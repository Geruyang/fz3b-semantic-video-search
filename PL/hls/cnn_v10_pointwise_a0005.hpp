#pragma once

// Included inside cnn_pipeline_v10.cpp's private namespace. Four output lanes
// by sixteen reduction lanes give 64 exact signed INT16 MACs per PW engine.
typedef ap_uint<192> AccColumn;
// Only the normal-profile PW2 persistent state and its result FIFO use this
// representation.  Arithmetic stays signed48 and P3 remains on AccColumn.
typedef ::cnn_v10_candidate::Pw2StoredColumn Pw2StoredColumn;
typedef ap_uint<152> ScaleGroup;

static AccColumn cnn_v10_pw2_expand_column(const Pw2StoredColumn& stored) {
#pragma HLS INLINE
    AccColumn expanded=0;
    for(unsigned lane=0;lane<4;++lane) {
#pragma HLS UNROLL
        expanded.range(lane*48+47,lane*48)=
            ap_uint<48>(::cnn_v10_candidate::pw2_expand_lane(stored,lane));
    }
    return expanded;
}

// The full 2048-column pair decouples final-r compute from residual/scale/DDR
// postprocessing. Smaller compile-time candidates remain available for the
// resource/performance study, but are not treated as a free capacity cut.
#ifndef CNN_V10_PW2_COLUMNS_DEPTH
#define CNN_V10_PW2_COLUMNS_DEPTH 1024
#endif
#if CNN_V10_PW2_COLUMNS_DEPTH < 16 || CNN_V10_PW2_COLUMNS_DEPTH > 2048
#error CNN_V10_PW2_COLUMNS_DEPTH must be in [16,2048]
#endif
#if CNN_V10_PW2_COLUMNS_DEPTH >= 2048
#define CNN_V10_PW2_SCALES_DEPTH 64
#elif CNN_V10_PW2_COLUMNS_DEPTH >= 1024
#define CNN_V10_PW2_SCALES_DEPTH 32
#elif CNN_V10_PW2_COLUMNS_DEPTH >= 512
#define CNN_V10_PW2_SCALES_DEPTH 16
#elif CNN_V10_PW2_COLUMNS_DEPTH >= 256
#define CNN_V10_PW2_SCALES_DEPTH 8
#elif CNN_V10_PW2_COLUMNS_DEPTH >= 128
#define CNN_V10_PW2_SCALES_DEPTH 4
#elif CNN_V10_PW2_COLUMNS_DEPTH >= 64
#define CNN_V10_PW2_SCALES_DEPTH 2
#else
#define CNN_V10_PW2_SCALES_DEPTH 1
#endif

template<int CORE_ID,bool FINAL,int BANK_DEPTH>
void pointwise_compute(hls::stream<pixel>& in,hls::stream<tile>& weights,
                       hls::stream<AccColumn>& columns,
                       hls::stream<ScaleGroup>& scales,
                       unsigned ic,unsigned oc,unsigned w,const coeff* co) {
#pragma HLS INLINE off
    // Pair logical lanes (0,1), (2,3), ... into one true-dual-port bank.
    // Each parity owns one 2*BANK_DEPTH half.  Load performs one write/cycle;
    // compute performs two fixed-address reads from every physical bank.
    pixel row[8][4*BANK_DEPTH];
#pragma HLS ARRAY_PARTITION variable=row complete dim=1
#pragma HLS BIND_STORAGE variable=row type=ram_t2p impl=bram
    const unsigned row_shift=cnn_v10_row_shift(w);
    const unsigned oc_groups=cnn_v10_oc_groups(oc);
    for(unsigned y=0;y<w;y+=2) {
        for(unsigned rr=0;rr<2;++rr)
            for(unsigned ch=0;ch<ic;++ch)
                for(unsigned x=0;x<w;++x) {
#pragma HLS PIPELINE II=1
                    const unsigned logical_address=
                        rr*BANK_DEPTH+((ch>>4)<<row_shift)+x;
                    const ::cnn_v10_candidate::Pw1PhysicalLocation location=
                        ::cnn_v10_candidate::pw1_physical_location(
                            ch&15,logical_address,2*BANK_DEPTH);
#ifndef __SYNTHESIS__
                    assert(location.accepted && location.physical_bank<8 &&
                           location.port<2 &&
                           location.physical_address<4*BANK_DEPTH);
#endif
                    row[location.physical_bank][location.physical_address]=in.read();
                }
        for(unsigned group=0,base_ch=0;group<oc_groups;++group,base_ch+=4) {
            ap_int<48> accum[4][128];coeff cs[4];
#pragma HLS ARRAY_PARTITION variable=accum complete dim=1
#pragma HLS BIND_STORAGE variable=accum type=ram_s2p impl=lutram
#pragma HLS ARRAY_PARTITION variable=cs complete
            for(unsigned l=0;l<4;++l) {
#pragma HLS PIPELINE II=1
                cs[l]=co[base_ch+l];
            }
            ScaleGroup header=0;
            for(unsigned l=0;l<4;++l) {
#pragma HLS UNROLL
                header.range(l*38+31,l*38)=ap_uint<32>(cs[l].mul);
                header.range(l*38+37,l*38+32)=cs[l].shift;
            }
            scales.write(header);
            // Keep the reduction group outside the pipelined pixel loop.  The
            // flattened form remained II=2 in HLS004/005 despite a physical
            // 1R1W accumulator and proven address distance.  This established
            // V9 structure is the deterministic scheduling fallback; its
            // per-group fill/drain cost remains subject to RTL performance.
            for(unsigned r=0;r<ic/16;++r) {
                tile wt=weights.read();
                for(unsigned z=0;z<2*w;++z) {
#pragma HLS PIPELINE II=1
                    unsigned rr=z>=w,x=rr?z-w:z;
                    pixel v[16];
#pragma HLS ARRAY_PARTITION variable=v complete
                    for(unsigned bank=0;bank<8;++bank) {
#pragma HLS UNROLL
                        const unsigned logical_address=
                            rr*BANK_DEPTH+(r<<row_shift)+x;
                        v[2*bank]=row[bank][logical_address];
                        v[2*bank+1]=row[bank][2*BANK_DEPTH+logical_address];
                    }
                    AccColumn column=0;
                    for(unsigned l=0;l<4;++l) {
#pragma HLS UNROLL
                        const ap_int<48> prior=r?accum[l][z]:cs[l].bias;
                        const ap_int<48> value=
                            cnn_v10_pw_dsp16_call(prior,v,wt,l);
                        accum[l][z]=value;
                        column.range(l*48+47,l*48)=ap_uint<48>(value);
                    }
                    if(r+1==ic/16) columns.write(column);
                }
            }
        }
    }
}

// PW2 consumes the group-major PW1 stream four groups (sixteen channels) at a
// time.  Making the reduction tile the outer loop bounds the interval in which
// PW2 does not read its input and removes the full-pair row store.  PW2 weights
// are packed r outer, output-group inner; the 4x16 tile lane layout is unchanged.
template<int CORE_ID>
void pointwise_compute_final_streaming(hls::stream<pixel>& in,
                       hls::stream<tile>& weights,
                       hls::stream<Pw2StoredColumn>& columns,
                       hls::stream<ScaleGroup>& scales,
                       unsigned c,unsigned w,const coeff* co) {
#pragma HLS INLINE off
    pixel input_tile[16][128];
#pragma HLS ARRAY_PARTITION variable=input_tile complete dim=1
#pragma HLS BIND_STORAGE variable=input_tile type=ram_s2p impl=lutram
    // (C/4)*(2W) is 2048 for all legal V10 profiles.  One packed word keeps
    // the four output lanes on a single 1R1W address.
    Pw2StoredColumn accum_all[2048];
#pragma HLS BIND_STORAGE variable=accum_all type=ram_s2p impl=bram
    const unsigned row_shift=cnn_v10_row_shift(w);
    const unsigned pair_span=2*w;
    const unsigned reductions=3*c/16;
    const unsigned oc_groups=cnn_v10_oc_groups(c);
    for(unsigned y=0;y<w;y+=2) {
        for(unsigned r=0;r<reductions;++r) {
            // PW1 emits each four-channel group as rr -> lane -> x.  Four
            // groups exactly populate the sixteen independently read banks.
            for(unsigned source_group=0;source_group<4;++source_group)
                for(unsigned rr=0;rr<2;++rr)
                    for(unsigned l=0;l<4;++l)
                        for(unsigned x=0;x<w;++x) {
#pragma HLS PIPELINE II=1
                            input_tile[source_group*4+l][(rr<<row_shift)+x]=in.read();
                        }
            for(unsigned group=0,base_ch=0,accum_base=0;
                group<oc_groups;
                ++group,base_ch+=4,accum_base+=pair_span) {
                tile wt=weights.read();
                coeff cs[4];
#pragma HLS ARRAY_PARTITION variable=cs complete
                if(r==0 || r+1==reductions) {
                    for(unsigned l=0;l<4;++l) {
#pragma HLS PIPELINE II=1
                        cs[l]=co[base_ch+l];
                    }
                }
                if(r+1==reductions) {
                    ScaleGroup header=0;
                    for(unsigned l=0;l<4;++l) {
#pragma HLS UNROLL
                        header.range(l*38+31,l*38)=ap_uint<32>(cs[l].mul);
                        header.range(l*38+37,l*38+32)=cs[l].shift;
                    }
                    scales.write(header);
                }
                for(unsigned z=0;z<2*w;++z) {
#pragma HLS PIPELINE II=1
                    pixel v[16];
#pragma HLS ARRAY_PARTITION variable=v complete
                    for(unsigned k=0;k<16;++k) {
#pragma HLS UNROLL
                        v[k]=input_tile[k][z];
                    }
                    // Sequential base generation avoids a runtime group-by-width
                    // multiply or variable barrel shift in the persistent RAM
                    // address path.
                    const unsigned address=accum_base+z;
                    Pw2StoredColumn prior_packed=
                        r?accum_all[address]:Pw2StoredColumn(0);
                    ap_int<48> lane_values[4];
#pragma HLS ARRAY_PARTITION variable=lane_values complete
                    for(unsigned l=0;l<4;++l) {
#pragma HLS UNROLL
                        const ap_int<48> prior=r
                            ? ::cnn_v10_candidate::pw2_expand_lane(prior_packed,l)
                            : cs[l].bias;
                        const ap_int<48> value=
                            cnn_v10_pw_dsp16_call(prior,v,wt,l);
                        lane_values[l]=value;
                    }
                    const Pw2StoredColumn column=
                        ::cnn_v10_candidate::pw2_pack_column(lane_values);
                    if(r+1==reductions) columns.write(column);
                    else accum_all[address]=column;
                }
            }
        }
    }
}

template<int CORE_ID>
void pointwise_post_expand(hls::stream<AccColumn>& columns,
                           hls::stream<ScaleGroup>& scales,
                           hls::stream<pixel>& out,unsigned oc,unsigned w,
                           const cnn_v10::SegmentedGelu& gelu,unsigned n,
                           volatile ap_uint<32>& trace,unsigned gelu_begin,
                           unsigned gelu_zero,unsigned gelu_tail,bool folded) {
#pragma HLS INLINE off
    AccColumn group_values[128];
#pragma HLS BIND_STORAGE variable=group_values type=ram_s2p impl=bram
    const unsigned row_shift=cnn_v10_row_shift(w);
    const unsigned oc_groups=cnn_v10_oc_groups(oc);
    for(unsigned y=0;y<w;y+=2) {
        for(unsigned group=0,base_ch=0;group<oc_groups;++group,base_ch+=4) {
            ScaleGroup header=scales.read();
            for(unsigned z=0;z<2*w;++z) {
#pragma HLS PIPELINE II=1
                group_values[z]=columns.read();
            }
            trace=0x80000000u|(n<<16)|(y<<8)|0x31u;
            for(unsigned rr=0;rr<2;++rr)
                for(unsigned l=0;l<4;++l) {
                    unsigned ch=base_ch+l;
                    ap_int<32> mul=header.range(l*38+31,l*38);
                    ap_uint<6> shift=header.range(l*38+37,l*38+32);
                    for(unsigned x=0;x<w;++x) {
#pragma HLS PIPELINE II=1
                        AccColumn packed=group_values[(rr<<row_shift)+x];
                        ap_int<48> raw=packed.range(l*48+47,l*48);
                        pixel q=clip(cnn_v10::scale(raw,mul,shift));
                        ap_uint<16> ix=ap_int<17>(q)+32768;
                        pixel value=folded?cnn_v10::segmented_folded_gelu(q,gelu):
                            (ix<gelu_zero?pixel(0):
                             ix>=gelu_tail?pixel(32767):
                             gelu.lookup(unsigned(ix-gelu_begin)));
                        out.write(value);
                    }
                }
        }
        trace=0x80000000u|(n<<16)|(y<<8)|0x32u;
    }
}

template<int CORE_ID,typename SCALE_CLIENT>
void pointwise_post_final(hls::stream<Pw2StoredColumn>& columns,
                          hls::stream<ScaleGroup>& scales,
                          cnn_v10::ParamReader& residual_reader,
                          hls::stream<ap_uint<32> >& residual_ready,
                          hls::stream<ap_uint<1> >& residual_release,
                          cnn_v10::DdrWriter& writer,
                          hls::stream<cnn_v10::RowReadyToken>& row_ready,
                          unsigned c,unsigned w,const ap_int<32>* sm,
                          const ap_uint<6>* ss,ap_int<32> rm,ap_uint<6> rs,
                          unsigned n,unsigned slot_words,SCALE_CLIENT& wide_scale,
                          volatile ap_uint<32>& trace) {
#pragma HLS INLINE off
    AccColumn group_values[128];
#pragma HLS BIND_STORAGE variable=group_values type=ram_s2p impl=bram
    const unsigned row_shift=cnn_v10_row_shift(w),oc_groups=cnn_v10_oc_groups(c);
    const unsigned output_base=((n+1)&1)?slot_words:0;
    unsigned pair_sequence=n*(w/2);
    for(unsigned y=0;y<w;y+=2,++pair_sequence) {
        ap_uint<32> token=residual_ready.read();
#ifndef __SYNTHESIS__
        assert(unsigned(token)==pair_sequence);
#endif
        unsigned scratch=2*slot_words+(pair_sequence&3)*CNN_V10_SCRATCH_CHUNK_WORDS;
        for(unsigned group=0,base_ch=0;group<oc_groups;++group,base_ch+=4) {
            ScaleGroup header=scales.read();
            for(unsigned z=0;z<2*w;++z) {
#pragma HLS PIPELINE II=1
                group_values[z]=cnn_v10_pw2_expand_column(columns.read());
            }
            trace=0x80000000u|(n<<16)|(y<<8)|0x31u;
            for(unsigned rr=0;rr<2;++rr) {
                const unsigned words=w/2;
                const unsigned channel_words=w/8;
                ap_uint<128> residual_words[32];
#pragma HLS BIND_STORAGE variable=residual_words type=ram_s2p impl=lutram
                residual_reader.request(scratch+rr*512+(base_ch<<row_shift)/8,words);
                writer.request(output_base+(y+rr)*512+(base_ch<<row_shift)/8,words);
                for(unsigned word=0;word<words;++word) {
#pragma HLS PIPELINE II=1
                    residual_words[word]=residual_reader.read();
                }
                // Keep one coefficient context for a complete channel.  The
                // service may retain up to 16 requests, so draining only at
                // channel boundaries amortizes the response-pipeline tail over
                // w=16/32/64 pixels rather than over every packed word.
                for(unsigned l=0;l<4;++l) {
                    const ap_int<32> mul=header.range(l*38+31,l*38);
                    const ap_uint<6> shift=header.range(l*38+37,l*38+32);
                    const ap_int<32> output_mul=sm[base_ch+l];
                    const ap_uint<6> output_shift=ss[base_ch+l];
                    ap_uint<7> sent=0,received=0;
                    ap_uint<5> inflight=0;
                    ap_uint<128> output_word=0,residual_shift=0;
                    while(received<w) {
#pragma HLS PIPELINE II=1
                        bool request_sent=false;
                        if(sent<w && inflight<16) {
                            AccColumn packed=group_values[(rr<<row_shift)+unsigned(sent)];
                            ap_int<48> raw=packed.range(l*48+47,l*48);
                            request_sent=wide_scale.try_request(raw,mul,shift);
                            if(request_sent) ++sent;
                        }
                        cnn_v10::ScaleResponse response;
                        const bool response_received=wide_scale.try_response(response);
                        ap_uint<5> next_inflight=inflight;
                        if(request_sent) ++next_inflight;
                        if(response_received) --next_inflight;
                        inflight=next_inflight;
#ifndef __SYNTHESIS__
                        assert(sent<=w && received<=sent && inflight<=16);
#endif
                        if(!response_received) continue;
                        const ap_uint<3> lane=received.range(2,0);
                        ap_uint<128> next_residual=residual_shift;
                        if(lane==0)
                            next_residual=residual_words[l*channel_words+(unsigned(received)>>3)];
                        pixel q=pixel(response);
                        pixel skip=pixel(next_residual.range(15,0));
                        pixel value=clip(cnn_v10::scale_narrow(q,output_mul,output_shift)+
                                         cnn_v10::scale_narrow(skip,rm,rs));
                        residual_shift=next_residual>>16;
                        // After eight fixed shifts, lane 0 reaches bits 15:0
                        // and lane 7 occupies bits 127:112, matching the ABI's
                        // little-endian 8xi16 word without a dynamic part set.
                        ap_uint<128> next_output=(output_word>>16)|
                            (ap_uint<128>(ap_uint<16>(value))<<112);
                        output_word=next_output;
                        if(lane==7) writer.write(next_output);
                        ++received;
#ifndef __SYNTHESIS__
                        assert(sent>=received && inflight==sent-received && inflight<=16);
#endif
                    }
#ifndef __SYNTHESIS__
                    assert(sent==w && received==w && inflight==0);
#endif
                }
                writer.commit();
            }
        }
        residual_release.write(1);
        row_ready.write(cnn_v10::pack_row_ready(n,y));
        row_ready.write(cnn_v10::pack_row_ready(n,y+1));
        trace=0x80000000u|(n<<16)|((y+1)<<8)|0x32u;
    }
}

template<int CORE_ID>
void pointwise_pair_expand(hls::stream<pixel>& in,hls::stream<tile>& weights,
                           hls::stream<pixel>& out,unsigned ic,unsigned oc,
                           unsigned w,
                           const coeff* co,const cnn_v10::SegmentedGelu& gelu,unsigned n,
                           volatile ap_uint<32>& trace,unsigned gelu_begin,
                           unsigned gelu_zero,unsigned gelu_tail,bool folded) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<AccColumn> columns("pw1_columns");hls::stream<ScaleGroup> scales("pw1_scales");
#pragma HLS STREAM variable=columns depth=128
#pragma HLS STREAM variable=scales depth=4
#pragma HLS BIND_STORAGE variable=columns type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=scales type=fifo impl=lutram
#ifdef __SYNTHESIS__
    pointwise_compute<CORE_ID,false,256>(in,weights,columns,scales,ic,oc,w,co);
    pointwise_post_expand<CORE_ID>(columns,scales,out,oc,w,gelu,n,trace,
                                   gelu_begin,gelu_zero,gelu_tail,folded);
#else
    NativeTaskBatch tasks(2);
    std::thread compute([&]{NativeTaskExit done(tasks);pointwise_compute<CORE_ID,false,256>(in,weights,columns,scales,ic,oc,w,co);});
    std::thread post([&]{NativeTaskExit done(tasks);pointwise_post_expand<CORE_ID>(columns,scales,out,oc,w,gelu,n,trace,gelu_begin,gelu_zero,gelu_tail,folded);});
    compute.join(); post.join();
#endif
}

template<int CORE_ID,typename SCALE_CLIENT>
void pointwise_pair_final(hls::stream<pixel>& in,hls::stream<tile>& weights,
                          cnn_v10::ParamReader& residual_reader,
                          hls::stream<ap_uint<32> >& residual_ready,
                          hls::stream<ap_uint<1> >& residual_release,
                          cnn_v10::DdrWriter& writer,
                          hls::stream<cnn_v10::RowReadyToken>& row_ready,
                          unsigned c,unsigned w,const coeff* co,const ap_int<32>* sm,
                          const ap_uint<6>* ss,ap_int<32> rm,ap_uint<6> rs,unsigned n,
                          unsigned slot_words,SCALE_CLIENT& wide_scale,
                          volatile ap_uint<32>& trace) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    hls::stream<Pw2StoredColumn> columns("pw2_columns");hls::stream<ScaleGroup> scales("pw2_scales");
#pragma HLS STREAM variable=columns depth=CNN_V10_PW2_COLUMNS_DEPTH
#pragma HLS STREAM variable=scales depth=CNN_V10_PW2_SCALES_DEPTH
#pragma HLS BIND_STORAGE variable=columns type=fifo impl=bram
#pragma HLS BIND_STORAGE variable=scales type=fifo impl=lutram
#ifdef __SYNTHESIS__
    pointwise_compute_final_streaming<CORE_ID>(in,weights,columns,scales,c,w,co);
    pointwise_post_final<CORE_ID>(columns,scales,residual_reader,residual_ready,residual_release,
                         writer,row_ready,c,w,sm,ss,rm,rs,n,slot_words,wide_scale,trace);
#else
    NativeTaskBatch tasks(2);
    std::thread compute([&]{NativeTaskExit done(tasks);pointwise_compute_final_streaming<CORE_ID>(in,weights,columns,scales,c,w,co);});
    std::thread post([&]{NativeTaskExit done(tasks);pointwise_post_final<CORE_ID>(columns,scales,residual_reader,residual_ready,residual_release,writer,row_ready,c,w,sm,ss,rm,rs,n,slot_words,wide_scale,trace);});
    compute.join(); post.join();
#endif
}
