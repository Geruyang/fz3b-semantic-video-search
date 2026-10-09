#include "cnn_pipeline_v10_a0005.hpp"
#include "cnn_v10_storage_contract.hpp"
#include "cnn_v10_storage_helpers.hpp"
#include "cnn_v10_pw2_storage.hpp"
#include "cnn_v10_param_broker.hpp"
#include "cnn_v10_arithmetic.hpp"
#include "cnn_v10_gelu.hpp"
#include "cnn_v10_gelu_segmented.hpp"
#include "cnn_v10_ddr.hpp"
#include "cnn_v10_n1.hpp"
#include "cnn_v10_scale_service.hpp"
#include "cnn_v10_pw_dsp.hpp"
#ifndef __SYNTHESIS__
#include <atomic>
#include <cassert>
#include <thread>
#endif

namespace {

#ifndef __SYNTHESIS__
struct NativeTaskBatch {
    std::atomic<unsigned> pending;
    explicit NativeTaskBatch(unsigned count):pending(count) {
        for(unsigned i=0;i<count;++i) hls::stream_globals::incr_task_counter();
    }
    void complete() { hls::stream_globals::decr_task_counter(); pending.fetch_sub(1); }
    ~NativeTaskBatch() {
        for(unsigned i=0;i<pending.load();++i) hls::stream_globals::decr_task_counter();
    }
};
struct NativeTaskExit {
    NativeTaskBatch& owner;
    explicit NativeTaskExit(NativeTaskBatch& batch):owner(batch) {}
    ~NativeTaskExit() { owner.complete(); }
};
#endif

typedef ap_int<16> pixel;
typedef ap_uint<1024> tile;
struct coeff { ap_int<48> bias; ap_int<32> mul; ap_uint<6> shift; };

using cnn_v10::ReadCmd;
using cnn_v10::ParamReader;
using cnn_v10::WriteCmd;
using cnn_v10::DdrWriter;

static pixel clip(ap_int<80> value) {
#pragma HLS INLINE
    return value>32767 ? pixel(32767) : value< -32767 ? pixel(-32767) : pixel(value);
}

static bool valid_metadata(const ap_uint<128>* p,unsigned c,unsigned blocks) {
    bool bad=false;
    unsigned base=0;
    for(unsigned n=0;n<blocks;++n) {
        const unsigned bias=base+cnn_v10_bias_offset(c);
        for(unsigned word=0;word<3*c;++word) {
#pragma HLS PIPELINE II=1
            ap_uint<128> value=p[bias+word];
            for(unsigned lane=0;lane<2;++lane) {
#pragma HLS UNROLL
                ap_int<64> raw=value.range(lane*64+63,lane*64);
                bad|=(raw!=ap_int<64>(ap_int<48>(raw)));
            }
        }
        const unsigned shifts=bias+3*c+6*c/4;
        for(unsigned word=0;word<6*c/4;++word) {
#pragma HLS PIPELINE II=1
            ap_uint<128> value=p[shifts+word];
            for(unsigned lane=0;lane<4;++lane) {
#pragma HLS UNROLL
                ap_int<32> raw=value.range(lane*32+31,lane*32);
                bad|=(raw<0 || raw>62);
            }
        }
        const unsigned residual=shifts+6*c/4;
        for(unsigned word=0;word<c/4;++word) {
#pragma HLS PIPELINE II=1
            ap_uint<128> value=p[residual+c/4+word];
            for(unsigned lane=0;lane<4;++lane) {
#pragma HLS UNROLL
                ap_int<32> raw=value.range(lane*32+31,lane*32);
                bad|=(raw<0 || raw>62);
            }
        }
        ap_uint<128> scalar=p[residual+c/2];
        ap_int<32> shift=scalar.range(63,32);
        bad|=(shift<0 || shift>62 || scalar.range(127,64)!=0);
        base+=cnn_v10_stride(c);
    }
    return !bad;
}

// ABI10 omits the analytically fixed zero prefix and saturated tail. The only
// redundant bytes left to validate are the zero padding after the retained
// compact interval in its fixed 7032-word slot.
static bool valid_gelu_padding(const ap_uint<128>* p,unsigned c,unsigned blocks,
                               unsigned profile) {
    bool bad=false;
    unsigned base=0;
    for(unsigned n=0;n<blocks;++n) {
        cnn_v10::GeluBound bound;
        if(!cnn_v10::gelu_bound(profile,n,bound)) return false;
        const unsigned used=cnn_v10::gelu_load_words(bound);
        const unsigned gelu=base+cnn_v10_gelu_offset(c);
        const unsigned begin=cnn_v10::gelu_load_begin(bound);
        if(used) {
            bad|=!cnn_v10::segmented_gelu_valid(p,gelu,used);
            ap_uint<128> first=p[gelu];
            ap_uint<128> last=p[gelu+used-1];
            for(unsigned lane=0;lane<8;++lane) {
#pragma HLS UNROLL
                const unsigned first_index=begin+lane;
                const unsigned last_index=begin+(used-1)*8+lane;
                pixel first_value=first.range(lane*16+15,lane*16);
                pixel last_value=last.range(lane*16+15,lane*16);
                if(first_index<bound.zero_prefix) bad|=(first_value!=0);
                if(last_index>=bound.tail_start) bad|=(last_value!=32767);
            }
        }
        for(unsigned word=used;word<cnn_v10::kGeluStorageWords;++word) {
#pragma HLS PIPELINE II=1
            bad|=(p[gelu+word]!=0);
        }
        base+=cnn_v10_stride(c);
    }
    return !bad;
}

static bool valid_n1_params(const ap_uint<128>* p) {
    bool bad=false;
    bad|=!cnn_v10::segmented_gelu_valid(
        p,cnn_v10::kN1DwGeluOffset,cnn_v10::kN1FoldedGeluWords);
    bad|=!cnn_v10::segmented_gelu_valid(
        p,cnn_v10::kN1PwGeluOffset,cnn_v10::kN1FoldedGeluWords);
    const unsigned shift_offsets[2]={cnn_v10::kN1DwShiftOffset,
                                     cnn_v10::kN1PwShiftOffset};
    for(unsigned stage=0;stage<2;++stage) {
        const unsigned bias=stage?cnn_v10::kN1PwBiasOffset:
                                   cnn_v10::kN1DwBiasOffset;
        for(unsigned word=0;word<64;++word) {
#pragma HLS PIPELINE II=1
            ap_uint<128> value=p[bias+word];
            for(unsigned lane=0;lane<2;++lane) {
#pragma HLS UNROLL
                ap_int<64> raw=value.range(lane*64+63,lane*64);
                bad|=(raw!=ap_int<64>(ap_int<48>(raw)));
            }
        }
        for(unsigned word=0;word<32;++word) {
#pragma HLS PIPELINE II=1
            ap_uint<128> value=p[shift_offsets[stage]+word];
            for(unsigned lane=0;lane<4;++lane) {
#pragma HLS UNROLL
                ap_int<32> raw=value.range(lane*32+31,lane*32);
                bad|=(raw<0 || raw>62);
            }
        }
    }
    return !bad;
}

static void load_i16(ParamReader& reader,unsigned base,unsigned count,pixel* out) {
    const unsigned words=count/8;
    for(unsigned pos=0;pos<words;pos+=32) {
#pragma HLS LOOP_FLATTEN off
        const unsigned len=(words-pos<32)?words-pos:32;
        reader.request(base+pos,len);
        for(unsigned j=0;j<len;++j) {
            ap_uint<128> value=reader.read();
            for(unsigned lane=0;lane<8;++lane) {
#pragma HLS PIPELINE II=1
                out[(pos+j)*8+lane]=pixel(value.range(lane*16+15,lane*16));
            }
        }
    }
}

// DW7 weights arrive in output-channel-major, tap-minor order.  Split even
// and odd output channels while unpacking the AXI words so each compute core
// gets one independent read port from each bank.  pair_base advances only
// after the odd channel of a pair; no runtime divide/modulo by 49 is needed.
static void load_dw7_i16_parity(ParamReader& reader,unsigned base,
                                unsigned channels,pixel* even,pixel* odd) {
#ifndef __SYNTHESIS__
    assert((channels&1)==0 && channels<=256);
#endif
    const unsigned words=(channels*49)/8;
    ap_uint<9> channel=0;
    ap_uint<6> tap=0;
    ap_uint<13> pair_base=0;
    for(unsigned pos=0;pos<words;pos+=32) {
#pragma HLS LOOP_FLATTEN off
        const unsigned len=(words-pos<32)?words-pos:32;
        reader.request(base+pos,len);
        for(unsigned j=0;j<len;++j) {
            ap_uint<128> value=reader.read();
            for(unsigned lane=0;lane<8;++lane) {
#pragma HLS PIPELINE II=1
                const pixel weight(value.range(lane*16+15,lane*16));
                const ap_uint<13> address=pair_base+tap;
                if(channel[0]) odd[address]=weight;
                else even[address]=weight;
                if(tap==48) {
                    tap=0;
                    if(channel[0]) pair_base=pair_base+49;
                    channel=channel+1;
                } else {
                    tap=tap+1;
                }
            }
        }
    }
#ifndef __SYNTHESIS__
    assert(channel==channels && tap==0 && pair_base==(channels/2)*49);
#endif
}

static void load_coeff(ParamReader& reader,unsigned base,unsigned c,
                       unsigned start,unsigned count,coeff* out) {
    const unsigned bias=base+cnn_v10_bias_offset(c);
    for(unsigned field=0;field<3;++field) {
        const unsigned packed=field?4:2;
        const unsigned at=field==0 ? bias+start/2 :
            bias+3*c+(field==2?6*c/4:0)+start/4;
        const unsigned words=count>>(field?2:1);
        for(unsigned pos=0;pos<words;pos+=32) {
#pragma HLS LOOP_FLATTEN off
            const unsigned len=(words-pos<32)?words-pos:32;
            reader.request(at+pos,len);
            for(unsigned j=0;j<len;++j) {
                ap_uint<128> value=reader.read();
                for(unsigned lane=0;lane<packed;++lane) {
#pragma HLS PIPELINE II=1
                    const unsigned index=((pos+j)<<(field?2:1))+lane;
                    if(field==0) out[index].bias=ap_int<64>(value.range(lane*64+63,lane*64));
                    else if(field==1) out[index].mul=ap_int<32>(value.range(lane*32+31,lane*32));
                    else out[index].shift=ap_uint<6>(value.range(lane*32+31,lane*32));
                }
            }
        }
    }
}

static void load_n1_coeff(ParamReader& reader,unsigned bias_offset,
                          unsigned multiplier_offset,unsigned shift_offset,
                          coeff* out) {
    for(unsigned pos=0;pos<64;pos+=32) {
#pragma HLS LOOP_FLATTEN off
        reader.request(bias_offset+pos,32);
        for(unsigned word=0;word<32;++word) {
            ap_uint<128> value=reader.read();
            for(unsigned lane=0;lane<2;++lane) {
#pragma HLS PIPELINE II=1
                out[(pos+word)*2+lane].bias=
                    ap_int<64>(value.range(lane*64+63,lane*64));
            }
        }
    }
    for(unsigned field=0;field<2;++field) {
#pragma HLS LOOP_FLATTEN off
        const unsigned offset=field?shift_offset:multiplier_offset;
        reader.request(offset,32);
        for(unsigned word=0;word<32;++word) {
            ap_uint<128> value=reader.read();
            for(unsigned lane=0;lane<4;++lane) {
#pragma HLS PIPELINE II=1
                const unsigned index=word*4+lane;
                if(field) out[index].shift=ap_uint<6>(
                    value.range(lane*32+31,lane*32));
                else out[index].mul=ap_int<32>(
                    value.range(lane*32+31,lane*32));
            }
        }
    }
}

static void load_residual(ParamReader& reader,unsigned base,unsigned c,
                          ap_int<32>* sm,ap_uint<6>* ss,
                          ap_int<32>& rm,ap_uint<6>& rs) {
    unsigned at=base+cnn_v10_bias_offset(c)+6*c;
    for(unsigned field=0;field<3;++field) {
        const unsigned words=field==2?1:c/4;
        for(unsigned pos=0;pos<words;pos+=32) {
#pragma HLS LOOP_FLATTEN off
            const unsigned len=(words-pos<32)?words-pos:32;
            reader.request(at+pos,len);
            for(unsigned j=0;j<len;++j) {
                ap_uint<128> value=reader.read();
                if(field==2) {
                    rm=ap_int<32>(value.range(31,0));
                    rs=ap_uint<6>(value.range(63,32));
                } else {
                    for(unsigned lane=0;lane<4;++lane) {
#pragma HLS PIPELINE II=1
                        const unsigned index=4*(pos+j)+lane;
                        if(field==0) sm[index]=ap_int<32>(value.range(lane*32+31,lane*32));
                        else ss[index]=ap_uint<6>(value.range(lane*32+31,lane*32));
                    }
                }
            }
        }
        at+=c/4;
    }
}

static void feed_chain(hls::stream<ReadCmd>& commands,
                       hls::stream<ap_uint<128> >& responses,
                       unsigned slot_words,unsigned w,unsigned blocks,
                       unsigned transition_stage,
                       hls::stream<cnn_v10::RowReadyToken>& row_ready,
                       hls::stream<pixel>& out,volatile ap_uint<32>& trace,
                       hls::stream<unsigned>& error) {
    ParamReader reader(commands,responses);
    unsigned bad=0; trace=0;
    for(unsigned n=0;n<blocks;++n) {
        const unsigned input_base=transition_stage==2?slot_words:
            ((n&1)?slot_words:0);
        for(unsigned y=0;y<w;++y) {
            if(n) {
                cnn_v10::RowReadyToken token=row_ready.read();
                if(token!=cnn_v10::pack_row_ready(n-1,y)) bad|=4;
            }
            for(unsigned pos=0;pos<512;pos+=32) {
                reader.request(input_base+y*512+pos,32);
                for(unsigned word=0;word<32;++word) {
                    ap_uint<128> value=reader.read();
                    for(unsigned lane=0;lane<8;++lane) {
#pragma HLS PIPELINE II=1
                        out.write(pixel(value.range(lane*16+15,lane*16)));
                    }
                }
            }
            trace=0x80000000u|(n<<16)|(y<<8)|0x11u;
        }
    }
    // PW2 produces one completion token for every output row. Consume the
    // final block too so a second ap_start cannot observe stale readiness.
    const unsigned output_rows=transition_stage?cnn_v10::kN1OutputWidth:w;
    for(unsigned y=0;y<output_rows;++y) {
        cnn_v10::RowReadyToken token=row_ready.read();
        if(token!=cnn_v10::pack_row_ready(blocks-1,y)) bad|=4;
    }
    reader.finish(); trace=0; error.write(bad);
}

template<bool SKIP> struct DwRawCodec;

template<> struct DwRawCodec<false> {
    typedef ap_uint<86> word;
    static word pack(ap_int<48> value,ap_int<32> multiplier,
                     ap_uint<6> shift,pixel) {
#pragma HLS INLINE
        word raw=0;
        raw.range(47,0)=ap_uint<48>(value);
        raw.range(79,48)=ap_uint<32>(multiplier);
        raw.range(85,80)=shift;
        return raw;
    }
    static pixel skip(const word&) {
#pragma HLS INLINE
        return 0;
    }
};

template<> struct DwRawCodec<true> {
    typedef ap_uint<102> word;
    static word pack(ap_int<48> value,ap_int<32> multiplier,
                     ap_uint<6> shift,pixel skip_value) {
#pragma HLS INLINE
        word raw=0;
        raw.range(47,0)=ap_uint<48>(value);
        raw.range(79,48)=ap_uint<32>(multiplier);
        raw.range(85,80)=shift;
        raw.range(101,86)=ap_uint<16>(skip_value);
        return raw;
    }
    static pixel skip(const word& raw) {
#pragma HLS INLINE
        return pixel(raw.range(101,86));
    }
};

template<int CORE_ID,int K,int LANES,bool SKIP>
static void depthwise_compute(hls::stream<pixel>& in,
                      hls::stream<typename DwRawCodec<SKIP>::word>& raw_out,
                       unsigned c,unsigned w,const pixel* weights_even,
                       const pixel* weights_odd,
                      const coeff* co,unsigned block,bool transition,
                      volatile ap_uint<32>& trace) {
#pragma HLS INLINE off
#pragma HLS ALLOCATION operation instances=mul limit=16
    typedef typename DwRawCodec<SKIP>::word RawWord;
    pixel rows[LANES][K][4096/LANES];
#pragma HLS ARRAY_PARTITION variable=rows complete dim=1
#pragma HLS BIND_STORAGE variable=rows type=ram_2p impl=bram
    if(K==7 && LANES==16) {
#ifndef __SYNTHESIS__
        assert(!transition || SKIP);
#endif
        // Normal DW7 and the N1 stride-2/depth-multiplier-2 transition share
        // this single syntactic sixteen-lane MAC.  Keeping the multiply below
        // the mode-dependent value/weight preparation prevents HLS from
        // allocating a second sixteen-DSP datapath for the runtime branch.
        // Even and odd output channels live in separate dual-read BRAM banks.
        // Each core reads one address from each bank per tap; normal mode
        // selects by channel parity and transition mode uses both values.
        RawWord output_pair[2][32];
#pragma HLS ARRAY_PARTITION variable=output_pair complete dim=1
#pragma HLS BIND_STORAGE variable=output_pair type=ram_s2p impl=lutram
        const unsigned radius=3;
        const unsigned input_c=transition?cnn_v10::kN1InputChannels:c;
        const unsigned input_w=transition?cnn_v10::kN1InputWidth:w;
        const unsigned output_w=transition?cnn_v10::kN1OutputWidth:w;
        const unsigned bank_shift=transition?2:(cnn_v10_row_shift(w)-4);
        ap_uint<3> input_slot=0;
        for(unsigned step=0;step<input_w+radius;++step) {
            ap_uint<4> center_slot=ap_uint<4>(input_slot)+1+radius;
            if(center_slot>=7) center_slot-=7;
            if(step<input_w) {
                for(unsigned ch=0;ch<input_c;++ch)
                    for(unsigned x=0;x<input_w;++x) {
#pragma HLS PIPELINE II=1
                        rows[x&15][input_slot][(ch<<bank_shift)+(x>>4)]=in.read();
                    }
                trace=0x80000000u|(block<<16)|(step<<8)|0x11u;
            }
            if(step>=radius) {
                const unsigned input_y=step-radius;
                if(!transition || (input_y&1)==0) {
                    const unsigned y=transition?(input_y>>1):input_y;
                    trace=0x80000000u|(block<<16)|(y<<8)|0x12u;
                    for(unsigned ch=0;ch<input_c;++ch) {
                        coeff cs[2];
#pragma HLS ARRAY_PARTITION variable=cs complete
                        cs[0]=co[transition?2*ch:ch];
                        cs[1]=transition?co[2*ch+1]:cs[0];
                        const unsigned xb_step=transition?8:16;
                        for(unsigned xb=0;xb<output_w;xb+=xb_step) {
                            ap_int<48> accum[16];
#pragma HLS ARRAY_PARTITION variable=accum complete
                            for(unsigned lane=0;lane<16;++lane) {
#pragma HLS UNROLL
                                accum[lane]=cs[transition?(lane>>3):0].bias;
                            }
                            for(int ky=0;ky<7;++ky) {
                                for(int kx=0;kx<7;++kx) {
#pragma HLS PIPELINE II=1
                                    const int yy=int(input_y)+ky-3;
                                    const int dx=kx-3;
                                    ap_uint<4> row_slot=ap_uint<4>(input_slot)+1+ky;
                                    if(row_slot>=7) row_slot-=7;
                                    pixel bank_values[16],mac_values[16],lane_weights[16];
#pragma HLS ARRAY_PARTITION variable=bank_values complete
#pragma HLS ARRAY_PARTITION variable=mac_values complete
#pragma HLS ARRAY_PARTITION variable=lane_weights complete
                                    const unsigned tap=unsigned(ky)*7+unsigned(kx);
                                    const unsigned pair_channel=transition?ch:(ch>>1);
                                    const unsigned address=pair_channel*49+tap;
                                    // Exactly one syntactic read from each parity bank per
                                    // core/tap.  Keep the mode mux after both reads so HLS
                                    // cannot infer separate normal/transition RAM ports.
                                    const pixel even_weight=weights_even[address];
                                    const pixel odd_weight=weights_odd[address];
                                    const pixel weight0=transition ? even_weight :
                                        ((ch&1)?odd_weight:even_weight);
                                    const pixel weight1=transition ? odd_weight : weight0;
                                    // Read every physical bank exactly once.  The
                                    // selected x coordinate is constructed so its
                                    // low four bits equal the fixed bank number.
                                    // Invalid padding uses a legal address first and
                                    // is masked only after the fixed-bank RAM read.
                                    const int base_x=transition ? 2*int(xb) : int(xb);
                                    for(unsigned bank=0;bank<16;++bank) {
#pragma HLS UNROLL
                                        const cnn_v10_candidate::Dw7FixedRead read=
                                            cnn_v10_candidate::dw7_fixed_bank_read(
                                                input_w,ch,bank_shift,yy,base_x,dx,bank);
                                        const pixel fetched=
                                            rows[bank][row_slot][read.address];
                                        bank_values[bank]=read.valid?fetched:pixel(0);
                                    }
                                    if(transition) {
                                        for(unsigned lane=0;lane<8;++lane) {
#pragma HLS UNROLL
                                            const unsigned bank=
                                                cnn_v10_candidate::dw7_p3_source_bank(lane,dx);
                                            const pixel value=bank_values[bank];
                                            mac_values[lane]=value;
                                            mac_values[lane+8]=value;
                                            lane_weights[lane]=weight0;
                                            lane_weights[lane+8]=weight1;
                                        }
                                    } else {
                                        for(unsigned lane=0;lane<16;++lane) {
#pragma HLS UNROLL
                                            const unsigned bank=
                                                cnn_v10_candidate::dw7_normal_source_bank(lane,dx);
                                            mac_values[lane]=bank_values[bank];
                                            lane_weights[lane]=weight0;
                                        }
                                    }
                                    // The only sixteen-wide DW7 multiply site.
                                    for(unsigned lane=0;lane<16;++lane) {
#pragma HLS UNROLL
                                        accum[lane]+=ap_int<32>(mac_values[lane])*lane_weights[lane];
                                    }
                                }
                            }
                            if(transition) {
                                for(unsigned lane=0;lane<16;++lane) {
#pragma HLS PIPELINE II=1
                                    const unsigned m=lane>>3;
                                    output_pair[m][xb+(lane&7)]=DwRawCodec<SKIP>::pack(
                                        accum[lane],cs[m].mul,cs[m].shift,pixel(0));
                                }
                            } else {
                                for(unsigned lane=0;lane<16;++lane) {
#pragma HLS PIPELINE II=1
                                    const pixel skip_value=SKIP ? rows[lane][center_slot][
                                        (ch<<bank_shift)+(xb>>4)] : pixel(0);
                                    raw_out.write(DwRawCodec<SKIP>::pack(
                                        accum[lane],cs[0].mul,cs[0].shift,skip_value));
                                }
                            }
                        }
                        if(transition)
                            for(unsigned m=0;m<2;++m)
                                for(unsigned x=0;x<cnn_v10::kN1OutputWidth;++x) {
#pragma HLS PIPELINE II=1
                                    raw_out.write(output_pair[m][x]);
                                }
                    }
                    trace=0x80000000u|(block<<16)|(y<<8)|0x13u;
                }
            }
            input_slot=(input_slot==6)?ap_uint<3>(0):ap_uint<3>(input_slot+1);
        }
        return;
    }
#ifndef __SYNTHESIS__
    assert(!transition);
#endif
    const unsigned radius=K/2;
    const unsigned lane_shift=LANES==16?4:2;
    const unsigned bank_shift=cnn_v10_row_shift(w)-lane_shift;
    ap_uint<3> input_slot=0;
    for(unsigned step=0;step<w+radius;++step) {
        ap_uint<4> center_slot=ap_uint<4>(input_slot)+1+radius;
        if(center_slot>=K) center_slot-=K;
        if(step<w) {
            for(unsigned ch=0;ch<c;++ch)
                for(unsigned x=0;x<w;++x) {
#pragma HLS PIPELINE II=1
                    rows[x&(LANES-1)][input_slot][(ch<<bank_shift)+x/LANES]=in.read();
                }
            trace=0x80000000u|(block<<16)|(step<<8)|0x11u;
        }
        if(step>=radius) {
            const unsigned y=step-radius;
            trace=0x80000000u|(block<<16)|(y<<8)|0x12u;
            unsigned weight_base=0;
            for(unsigned ch=0;ch<c;++ch) {
                for(unsigned xb=0;xb<w;xb+=LANES) {
                    ap_int<48> accum[LANES];
#pragma HLS ARRAY_PARTITION variable=accum complete
                    const coeff ct=co[ch];
                    for(unsigned lane=0;lane<LANES;++lane) {
#pragma HLS UNROLL
                        accum[lane]=ct.bias;
                    }
                    for(int ky=0;ky<K;++ky) {
                        for(int kx=0;kx<K;++kx) {
#pragma HLS PIPELINE II=1
                            const int yy=int(y)+ky-int(radius);
                            const int dx=kx-int(radius);
                            ap_uint<4> row_slot=ap_uint<4>(input_slot)+1+ky;
                            if(row_slot>=K) row_slot-=K;
                            pixel values[LANES];
#pragma HLS ARRAY_PARTITION variable=values complete
                            for(unsigned bank=0;bank<LANES;++bank) {
#pragma HLS UNROLL
                                const int xx=int(xb)+((int(bank)-dx)&(LANES-1))+dx;
                                values[bank]=(yy>=0 && yy<int(w) && xx>=0 && xx<int(w))
                                    ? rows[bank][row_slot][(ch<<bank_shift)+unsigned(xx)/LANES]
                                    : pixel(0);
                            }
                            const pixel weight=weights_even[weight_base+ky*K+kx];
                            for(unsigned lane=0;lane<LANES;++lane) {
#pragma HLS UNROLL
                                const unsigned bank=(int(lane)+dx)&(LANES-1);
                                accum[lane]+=ap_int<32>(values[bank])*weight;
                            }
                        }
                    }
                    // Emit one compact record per service request.  The
                    // separate quantization process can keep requests in
                    // flight while this process starts the next MAC group.
                    for(unsigned lane=0;lane<LANES;++lane) {
#pragma HLS PIPELINE II=1
                        const pixel skip_value=SKIP ? rows[lane][center_slot][
                            (ch<<bank_shift)+xb/LANES] : pixel(0);
                        raw_out.write(DwRawCodec<SKIP>::pack(
                            accum[lane],ct.mul,ct.shift,skip_value));
                    }
                }
                weight_base+=K*K;
            }
            trace=0x80000000u|(block<<16)|(y<<8)|0x13u;
        }
        input_slot=(input_slot==K-1)?ap_uint<3>(0):ap_uint<3>(input_slot+1);
    }
}

template<int CORE_ID,bool SKIP>
static void depthwise_emit(
        hls::stream<typename DwRawCodec<SKIP>::word>& raw_in,
        hls::stream<pixel>& out,hls::stream<pixel>& residual,
        unsigned c,unsigned w,bool emit_skip,
        cnn_v10::ScaleClient& scale_client) {
#pragma HLS INLINE off
    typedef typename DwRawCodec<SKIP>::word RawWord;
    pixel skip_ring[16];
#pragma HLS BIND_STORAGE variable=skip_ring type=ram_s2p impl=lutram
    // One invocation handles one block.  The largest profile has exactly
    // 262144 outputs, so the inclusive terminal count requires 19 bits.
    // All legal V10 profiles satisfy C*W=4096; avoid four dynamic DSP multiplies.
    const ap_uint<19> total=ap_uint<19>(w)<<12;
    ap_uint<19> accepted=0,received=0;
    ap_uint<5> inflight=0;
    ap_uint<4> head=0,tail=0;
    RawWord pending[2];
#pragma HLS ARRAY_PARTITION variable=pending complete dim=1
    ap_uint<1> pending_head=0,pending_tail=0;
    ap_uint<2> pending_count=0;
    ap_uint<19> fetched=0;
    while(received<total) {
#pragma HLS PIPELINE II=1
        // Two registered slots isolate FIFO refill from request acceptance.
        // Push eligibility uses only the old count.  When a full skid pops, it
        // deliberately waits one cycle before reading raw_in again, cutting
        // sent/request/inflight feedback out of the FIFO read-enable path.
        RawWord candidate=0;
        if(pending_count!=0) candidate=pending[pending_head];
        bool sent=false;
        if(pending_count!=0 && inflight<16) {
            sent=scale_client.try_request(
                ap_int<48>(candidate.range(47,0)),
                ap_int<32>(candidate.range(79,48)),
                ap_uint<6>(candidate.range(85,80)));
            if(sent) {
                if(SKIP) skip_ring[tail]=DwRawCodec<SKIP>::skip(candidate);
                tail=tail+1;
                ++accepted;
            }
        }
        RawWord refill=0;
        bool pushed=false;
        if(pending_count<2 && fetched<total)
            pushed=raw_in.read_nb(refill);
        if(pushed) {
            pending[pending_tail]=refill;
            pending_tail=pending_tail+1;
            ++fetched;
        }
        if(sent) pending_head=pending_head+1;
        if(pushed&&!sent) ++pending_count;
        else if(sent&&!pushed) --pending_count;

        cnn_v10::ScaleResponse response;
        const bool returned=scale_client.try_response(response);
#ifndef __SYNTHESIS__
        // A response may return in the same native iteration as the first
        // request, but never without a prior or newly accepted request.
        if(returned) assert(inflight!=0 || sent);
#endif
        if(returned) {
            out.write(pixel(response));
            if(SKIP && emit_skip) residual.write(skip_ring[head]);
            head=head+1;
            ++received;
        }
        ap_uint<5> next_inflight=inflight;
        if(sent) ++next_inflight;
        if(returned) --next_inflight;
        inflight=next_inflight;
#ifndef __SYNTHESIS__
        assert(accepted>=received);
        assert(fetched>=accepted);
        assert(inflight==accepted-received);
        assert(inflight<=16);
        assert(pending_count==fetched-accepted);
        assert(pending_count<=2 && fetched<=total);
#endif
    }
#ifndef __SYNTHESIS__
    assert(fetched==total && accepted==total && received==total &&
           inflight==0 && pending_count==0);
#endif
}

template<int K,int LANES,bool SKIP>
static void depthwise_dual(hls::stream<pixel>& in_a,hls::stream<pixel>& out_a,
                           hls::stream<pixel>& residual_a,
                           hls::stream<pixel>& in_b,hls::stream<pixel>& out_b,
                           hls::stream<pixel>& residual_b,unsigned c,unsigned w,
                           const pixel* weights_even,const pixel* weights_odd,
                           const coeff* co,unsigned block,
                           bool transition,bool emit_skip,
                           cnn_v10::ScaleClient& scale_a,
                           cnn_v10::ScaleClient& scale_b,
                           volatile ap_uint<32>& trace_a,
                           volatile ap_uint<32>& trace_b) {
#pragma HLS INLINE off
    hls::stream<typename DwRawCodec<SKIP>::word> raw_a("dw_raw_a"),raw_b("dw_raw_b");
#pragma HLS STREAM variable=raw_a depth=16
#pragma HLS STREAM variable=raw_b depth=16
#pragma HLS BIND_STORAGE variable=raw_a type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=raw_b type=fifo impl=lutram
#pragma HLS DATAFLOW
#ifdef __SYNTHESIS__
    depthwise_compute<0,K,LANES,SKIP>(in_a,raw_a,c,w,weights_even,weights_odd,
                                      co,block,transition,trace_a);
    depthwise_emit<0,SKIP>(raw_a,out_a,residual_a,c,w,emit_skip,scale_a);
    depthwise_compute<1,K,LANES,SKIP>(in_b,raw_b,c,w,weights_even,weights_odd,
                                      co,block,transition,trace_b);
    depthwise_emit<1,SKIP>(raw_b,out_b,residual_b,c,w,emit_skip,scale_b);
#else
    // Each emit task exclusively owns its ScaleClient debug state.  Native
    // streams are unbounded; bounded depth and backpressure remain RTL gates.
    NativeTaskBatch tasks(4);
    std::thread ca([&]{NativeTaskExit done(tasks);depthwise_compute<0,K,LANES,SKIP>(in_a,raw_a,c,w,weights_even,weights_odd,co,block,transition,trace_a);});
    std::thread ea([&]{NativeTaskExit done(tasks);depthwise_emit<0,SKIP>(raw_a,out_a,residual_a,c,w,emit_skip,scale_a);});
    std::thread cb([&]{NativeTaskExit done(tasks);depthwise_compute<1,K,LANES,SKIP>(in_b,raw_b,c,w,weights_even,weights_odd,co,block,transition,trace_b);});
    std::thread eb([&]{NativeTaskExit done(tasks);depthwise_emit<1,SKIP>(raw_b,out_b,residual_b,c,w,emit_skip,scale_b);});
    ca.join(); ea.join(); cb.join(); eb.join();
#endif
}

template<int K,int LANES,bool SKIP,int CLIENT>
static void depthwise_chain(hls::stream<ReadCmd>& commands,
                            hls::stream<ap_uint<128> >& responses,
                            hls::stream<pixel>& in_a,hls::stream<pixel>& out_a,
                            hls::stream<pixel>& residual_a,
                            hls::stream<pixel>& in_b,hls::stream<pixel>& out_b,
                            hls::stream<pixel>& residual_b,
                            hls::stream<cnn_v10::ScaleRequest>& req_a,
                            hls::stream<cnn_v10::ScaleResponse>& rsp_a,
                            hls::stream<cnn_v10::ScaleCredit>& ret_a,
                            hls::stream<cnn_v10::ScaleRequest>& req_b,
                            hls::stream<cnn_v10::ScaleResponse>& rsp_b,
                            hls::stream<cnn_v10::ScaleCredit>& ret_b,
                            unsigned c,unsigned w,unsigned blocks,
                            unsigned transition_stage,
                            volatile ap_uint<32>& trace_a,
                            volatile ap_uint<32>& trace_b) {
    ParamReader reader(commands,responses);
    cnn_v10::ScaleClient scale_a(req_a,rsp_a,ret_a),scale_b(req_b,rsp_b,ret_b);
    static pixel weights_even[K==7 ? 49*128 : 9*256];
    static pixel weights_odd[K==7 ? 49*128 : 1];
    static coeff co[256];
#pragma HLS BIND_STORAGE variable=weights_even type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=weights_odd type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=co type=ram_2p impl=bram
    trace_a=0; trace_b=0;
    if(transition_stage) {
        if(K==3 || transition_stage==2) {
            const unsigned total=transition_stage==1
                ? cnn_v10::kN1InputChannels*cnn_v10::kN1InputWidth*cnn_v10::kN1InputWidth
                : cnn_v10::kN1OutputChannels*cnn_v10::kN1OutputWidth*cnn_v10::kN1OutputWidth;
            for(unsigned index=0;index<total;++index) {
#pragma HLS PIPELINE II=1
                out_a.write(in_a.read());
                out_b.write(in_b.read());
            }
        } else {
            load_dw7_i16_parity(reader,cnn_v10::kN1DwWeightOffset,
                                cnn_v10::kN1OutputChannels,
                                weights_even,weights_odd);
            load_n1_coeff(reader,cnn_v10::kN1DwBiasOffset,
                          cnn_v10::kN1DwMultiplierOffset,
                          cnn_v10::kN1DwShiftOffset,co);
            depthwise_dual<K,LANES,SKIP>(
                in_a,out_a,residual_a,in_b,out_b,residual_b,
                cnn_v10::kN1OutputChannels,cnn_v10::kN1OutputWidth,
                weights_even,weights_odd,co,0,true,false,
                scale_a,scale_b,trace_a,trace_b);
        }
        reader.finish(); scale_a.finish(); scale_b.finish();
        trace_a=0; trace_b=0; return;
    }
    unsigned base=0;
    for(unsigned n=0;n<blocks;++n) {
        const unsigned count=K*K*c;
        const unsigned offset=K==3?0:(9*c/8);
        if(K==7)
            load_dw7_i16_parity(reader,base+offset,c,weights_even,weights_odd);
        else
            load_i16(reader,base+offset,count,weights_even);
        load_coeff(reader,base,c,K==3?0:c,c,co);
        depthwise_dual<K,LANES,SKIP>(in_a,out_a,residual_a,in_b,out_b,residual_b,
                                     c,w,weights_even,weights_odd,co,n,false,SKIP,
                                     scale_a,scale_b,trace_a,trace_b);
        base+=cnn_v10_stride(c);
    }
    reader.finish(); scale_a.finish(); scale_b.finish(); trace_a=0; trace_b=0;
}

static void residual_writer(hls::stream<pixel>& residual,
                            hls::stream<WriteCmd>& commands,
                            hls::stream<ap_uint<128> >& data,
                            hls::stream<ap_uint<1> >& committed,
                            hls::stream<ap_uint<32> >& ready,
                            hls::stream<ap_uint<1> >& release,
                            unsigned slot_words,unsigned w,unsigned blocks,
                            unsigned transition_stage,
                            volatile ap_uint<32>& trace) {
    DdrWriter writer(commands,data,committed);
    trace=0;
    if(transition_stage) { writer.finish(); return; }
    unsigned sequence=0;
    for(unsigned n=0;n<blocks;++n) {
        for(unsigned y=0;y<w;y+=2,++sequence) {
            if(sequence>=CNN_V10_SCRATCH_CHUNKS) (void)release.read();
            const unsigned scratch=2*slot_words+
                (sequence&(CNN_V10_SCRATCH_CHUNKS-1))*CNN_V10_SCRATCH_CHUNK_WORDS;
            for(unsigned rr=0;rr<2;++rr) {
                for(unsigned pos=0;pos<512;pos+=32) {
                    writer.request(scratch+rr*512+pos,32);
                    for(unsigned word=0;word<32;++word) {
                        ap_uint<128> value=0;
                        for(unsigned lane=0;lane<8;++lane) {
#pragma HLS PIPELINE II=1
                            value.range(lane*16+15,lane*16)=ap_uint<16>(residual.read());
                        }
                        writer.write(value);
                    }
                    writer.commit();
                }
            }
            ready.write(sequence);
            trace=0x80000000u|(n<<16)|((y+1)<<8)|0x21u;
        }
    }
    const unsigned tail=(sequence<CNN_V10_SCRATCH_CHUNKS)?sequence:CNN_V10_SCRATCH_CHUNKS;
    for(unsigned i=0;i<tail;++i) (void)release.read();
    writer.finish(); trace=0;
}

static void weight_broadcast(hls::stream<ReadCmd>& commands,
                             hls::stream<ap_uint<128> >& responses,
                             hls::stream<tile>& out_a,hls::stream<tile>& out_b,
                             unsigned c,unsigned w,unsigned blocks,bool final,
                             unsigned transition_stage) {
    ParamReader reader(commands,responses);
    if(transition_stage==1 || (transition_stage==2 && final)) {
        reader.finish(); return;
    }
    const bool transition=transition_stage==2;
    const unsigned run_c=transition?cnn_v10::kN1OutputChannels:c;
    const unsigned run_w=transition?cnn_v10::kN1OutputWidth:w;
    const unsigned run_blocks=transition?1:blocks;
    const unsigned count=transition ?
        (cnn_v10::kN1OutputChannels/4)*(cnn_v10::kN1OutputChannels/16) :
        cnn_v10_weight_tiles(c,final);
    unsigned base=transition?cnn_v10::kN1PwWeightOffset:
        (final?cnn_v10_pw2_offset(c):cnn_v10_pw1_offset(c));
    for(unsigned n=0;n<run_blocks;++n) {
        for(unsigned y=0;y<run_w;y+=2) {
            unsigned at=base;
            for(unsigned index=0;index<count;index+=4) {
#pragma HLS LOOP_FLATTEN off
                const unsigned pair=(count-index<4)?count-index:4;
                reader.request(at,pair*8);
                for(unsigned p=0;p<pair;++p) {
                    tile value=0;
                    for(unsigned word=0;word<8;++word) {
#pragma HLS PIPELINE II=1
                        value.range(word*128+127,word*128)=reader.read();
                    }
                    out_a.write(value); out_b.write(value);
                }
                at+=pair*8;
            }
        }
        if(!transition) base+=cnn_v10_stride(run_c);
    }
    reader.finish();
}

#include "cnn_v10_pointwise_a0005.hpp"

static void pointwise_expand_dual(hls::stream<pixel>& in_a,hls::stream<tile>& wt_a,
                                  hls::stream<pixel>& out_a,
                                  hls::stream<pixel>& in_b,hls::stream<tile>& wt_b,
                                  hls::stream<pixel>& out_b,unsigned ic,unsigned oc,
                                  unsigned w,
                                  const coeff* co,const cnn_v10::SegmentedGelu& gelu,unsigned n,
                                  unsigned begin,unsigned zero,unsigned tail,
                                  bool folded,
                                  volatile ap_uint<32>& trace_a,
                                  volatile ap_uint<32>& trace_b) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
#ifdef __SYNTHESIS__
    pointwise_pair_expand<0>(in_a,wt_a,out_a,ic,oc,w,co,gelu,n,trace_a,begin,zero,tail,folded);
    pointwise_pair_expand<1>(in_b,wt_b,out_b,ic,oc,w,co,gelu,n,trace_b,begin,zero,tail,folded);
#else
    NativeTaskBatch tasks(2);
    std::thread a([&]{NativeTaskExit done(tasks);pointwise_pair_expand<0>(in_a,wt_a,out_a,ic,oc,w,co,gelu,n,trace_a,begin,zero,tail,folded);});
    std::thread b([&]{NativeTaskExit done(tasks);pointwise_pair_expand<1>(in_b,wt_b,out_b,ic,oc,w,co,gelu,n,trace_b,begin,zero,tail,folded);});
    a.join(); b.join();
#endif
}

static void n1_folded_gelu_dual(hls::stream<pixel>& in_a,
                                hls::stream<pixel>& out_a,
                                hls::stream<pixel>& in_b,
                                hls::stream<pixel>& out_b,
                                const cnn_v10::SegmentedGelu& gelu,
                                volatile ap_uint<32>& trace_a,
                                volatile ap_uint<32>& trace_b) {
#pragma HLS INLINE off
    const unsigned row_pixels=cnn_v10::kN1OutputChannels*
                              cnn_v10::kN1OutputWidth;
    for(unsigned y=0;y<cnn_v10::kN1OutputWidth;++y) {
        for(unsigned index=0;index<row_pixels;++index) {
#pragma HLS PIPELINE II=1
            out_a.write(cnn_v10::segmented_folded_gelu(in_a.read(),gelu));
            out_b.write(cnn_v10::segmented_folded_gelu(in_b.read(),gelu));
        }
        trace_a=0x80000000u|(y<<8)|0x31u;
        trace_b=0x80000000u|(y<<8)|0x31u;
    }
}

static void pointwise1_chain(hls::stream<ReadCmd>& commands,
                             hls::stream<ap_uint<128> >& responses,
                             hls::stream<pixel>& in_a,hls::stream<tile>& wt_a,
                             hls::stream<pixel>& out_a,
                             hls::stream<pixel>& in_b,hls::stream<tile>& wt_b,
                             hls::stream<pixel>& out_b,unsigned c,unsigned w,
                             unsigned blocks,unsigned profile,
                             unsigned transition_stage,
                             volatile ap_uint<32>& trace_a,
                             volatile ap_uint<32>& trace_b) {
    ParamReader reader(commands,responses);
    static coeff co[768];
    static cnn_v10::SegmentedGelu gelu;
#pragma HLS BIND_STORAGE variable=co type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=gelu.base type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=gelu.low type=ram_2p impl=bram
    trace_a=0; trace_b=0;
    if(transition_stage==1) {
        cnn_v10::load_segmented_gelu(
            reader,cnn_v10::kN1DwGeluOffset,32768,gelu);
        n1_folded_gelu_dual(in_a,out_a,in_b,out_b,gelu,trace_a,trace_b);
        reader.finish(); trace_a=0; trace_b=0; return;
    }
    unsigned base=0;
    const unsigned iterations=transition_stage?1:blocks;
    for(unsigned n=0;n<iterations;++n) {
        cnn_v10::GeluBound bound;
        unsigned begin=0,zero=0,tail=0,ic=c,oc=3*c,run_w=w;
        bool folded=false;
        if(transition_stage==2) {
            cnn_v10::load_segmented_gelu(
                reader,cnn_v10::kN1PwGeluOffset,32768,gelu);
            load_n1_coeff(reader,cnn_v10::kN1PwBiasOffset,
                          cnn_v10::kN1PwMultiplierOffset,
                          cnn_v10::kN1PwShiftOffset,co);
            ic=cnn_v10::kN1OutputChannels;
            oc=cnn_v10::kN1OutputChannels;
            run_w=cnn_v10::kN1OutputWidth;
            folded=true;
        } else {
            (void)cnn_v10::gelu_bound(profile,n,bound);
            begin=cnn_v10::gelu_load_begin(bound);
            zero=bound.zero_prefix; tail=bound.tail_start;
            cnn_v10::load_segmented_gelu(
                reader,base+cnn_v10_gelu_offset(c),
                cnn_v10::gelu_load_words(bound)*8,gelu);
            load_coeff(reader,base,c,2*c,3*c,co);
            base+=cnn_v10_stride(c);
        }
        pointwise_expand_dual(in_a,wt_a,out_a,in_b,wt_b,out_b,ic,oc,run_w,
                              co,gelu,n,begin,zero,tail,folded,trace_a,trace_b);
    }
    reader.finish(); trace_a=0; trace_b=0;
}

static void pointwise_final_dual(
        hls::stream<pixel>& in_a,hls::stream<tile>& wt_a,
        ParamReader& residual_a,hls::stream<ap_uint<32> >& ready_a,
        hls::stream<ap_uint<1> >& release_a,DdrWriter& writer_a,
        hls::stream<cnn_v10::RowReadyToken>& row_ready_a,
        cnn_v10::ScaleClient& scale_a,
        hls::stream<pixel>& in_b,hls::stream<tile>& wt_b,
        ParamReader& residual_b,hls::stream<ap_uint<32> >& ready_b,
        hls::stream<ap_uint<1> >& release_b,DdrWriter& writer_b,
        hls::stream<cnn_v10::RowReadyToken>& row_ready_b,
        cnn_v10::ScaleClient& scale_b,
        unsigned c,unsigned w,const coeff* co_a,const coeff* co_b,
        const ap_int<32>* sm,
        const ap_uint<6>* ss,ap_int<32> rm,ap_uint<6> rs,unsigned n,
        unsigned slot_words,volatile ap_uint<32>& trace_a,
        volatile ap_uint<32>& trace_b) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
#ifdef __SYNTHESIS__
    pointwise_pair_final<0>(in_a,wt_a,residual_a,ready_a,release_a,writer_a,
                            row_ready_a,c,w,co_a,sm,ss,rm,rs,n,slot_words,scale_a,trace_a);
    pointwise_pair_final<1>(in_b,wt_b,residual_b,ready_b,release_b,writer_b,
                            row_ready_b,c,w,co_b,sm,ss,rm,rs,n,slot_words,scale_b,trace_b);
#else
    NativeTaskBatch tasks(2);
    std::thread a([&]{NativeTaskExit done(tasks);pointwise_pair_final<0>(in_a,wt_a,residual_a,
        ready_a,release_a,writer_a,row_ready_a,c,w,co_a,sm,ss,rm,rs,n,slot_words,scale_a,trace_a);});
    std::thread b([&]{NativeTaskExit done(tasks);pointwise_pair_final<1>(in_b,wt_b,residual_b,
        ready_b,release_b,writer_b,row_ready_b,c,w,co_b,sm,ss,rm,rs,n,slot_words,scale_b,trace_b);});
    a.join(); b.join();
#endif
}

static void n1_output_dual(hls::stream<pixel>& in_a,DdrWriter& writer_a,
                           hls::stream<cnn_v10::RowReadyToken>& row_ready_a,
                           hls::stream<pixel>& in_b,DdrWriter& writer_b,
                           hls::stream<cnn_v10::RowReadyToken>& row_ready_b,
                           unsigned output_base,bool group_pair_order,
                           volatile ap_uint<32>& trace_a,
                           volatile ap_uint<32>& trace_b) {
    if(group_pair_order) {
        // pointwise_post_expand emits one two-row/four-channel group at a
        // time: group -> row -> channel -> x.  Scatter each contiguous
        // 4*W chunk into its HCW row address instead of treating this stream
        // as a complete row.  For W=32 each chunk is exactly 16 AXI words.
        const unsigned words_per_group=4*cnn_v10::kN1OutputWidth/8;
        for(unsigned y=0;y<cnn_v10::kN1OutputWidth;y+=2) {
            for(unsigned group=0;group<cnn_v10::kN1OutputChannels/4;++group) {
                for(unsigned rr=0;rr<2;++rr) {
                    const unsigned address=output_base+(y+rr)*512+
                        group*words_per_group;
                    writer_a.request(address,words_per_group);
                    writer_b.request(address,words_per_group);
                    for(unsigned word=0;word<words_per_group;++word) {
                        ap_uint<128> value_a=0,value_b=0;
                        for(unsigned lane=0;lane<8;++lane) {
#pragma HLS PIPELINE II=1
                            value_a.range(lane*16+15,lane*16)=ap_uint<16>(in_a.read());
                            value_b.range(lane*16+15,lane*16)=ap_uint<16>(in_b.read());
                        }
                        writer_a.write(value_a); writer_b.write(value_b);
                    }
                    writer_a.commit(); writer_b.commit();
                }
            }
            row_ready_a.write(cnn_v10::pack_row_ready(0,y));
            row_ready_a.write(cnn_v10::pack_row_ready(0,y+1));
            row_ready_b.write(cnn_v10::pack_row_ready(0,y));
            row_ready_b.write(cnn_v10::pack_row_ready(0,y+1));
            trace_a=0x80000000u|((y+1)<<8)|0x32u;
            trace_b=0x80000000u|((y+1)<<8)|0x32u;
        }
        return;
    }
    for(unsigned y=0;y<cnn_v10::kN1OutputWidth;++y) {
        for(unsigned pos=0;pos<512;pos+=32) {
            writer_a.request(output_base+y*512+pos,32);
            writer_b.request(output_base+y*512+pos,32);
            for(unsigned word=0;word<32;++word) {
                ap_uint<128> value_a=0,value_b=0;
                for(unsigned lane=0;lane<8;++lane) {
#pragma HLS PIPELINE II=1
                    value_a.range(lane*16+15,lane*16)=ap_uint<16>(in_a.read());
                    value_b.range(lane*16+15,lane*16)=ap_uint<16>(in_b.read());
                }
                writer_a.write(value_a); writer_b.write(value_b);
            }
            writer_a.commit(); writer_b.commit();
        }
        row_ready_a.write(cnn_v10::pack_row_ready(0,y));
        row_ready_b.write(cnn_v10::pack_row_ready(0,y));
        trace_a=0x80000000u|(y<<8)|0x32u;
        trace_b=0x80000000u|(y<<8)|0x32u;
    }
}

static void pointwise2_chain(
        hls::stream<ReadCmd>& commands,hls::stream<ap_uint<128> >& responses,
        hls::stream<pixel>& in_a,hls::stream<tile>& wt_a,
        hls::stream<ReadCmd>& residual_commands_a,
        hls::stream<ap_uint<128> >& residual_responses_a,
        hls::stream<ap_uint<32> >& residual_ready_a,
        hls::stream<ap_uint<1> >& residual_release_a,
        hls::stream<WriteCmd>& write_commands_a,
        hls::stream<ap_uint<128> >& write_data_a,
        hls::stream<ap_uint<1> >& write_committed_a,
        hls::stream<cnn_v10::RowReadyToken>& row_ready_a,
        hls::stream<cnn_v10::ScaleRequest>& scale_req_a,
        hls::stream<cnn_v10::ScaleResponse>& scale_rsp_a,
        hls::stream<cnn_v10::ScaleCredit>& scale_ret_a,
        hls::stream<pixel>& in_b,hls::stream<tile>& wt_b,
        hls::stream<ReadCmd>& residual_commands_b,
        hls::stream<ap_uint<128> >& residual_responses_b,
        hls::stream<ap_uint<32> >& residual_ready_b,
        hls::stream<ap_uint<1> >& residual_release_b,
        hls::stream<WriteCmd>& write_commands_b,
        hls::stream<ap_uint<128> >& write_data_b,
        hls::stream<ap_uint<1> >& write_committed_b,
        hls::stream<cnn_v10::RowReadyToken>& row_ready_b,
        hls::stream<cnn_v10::ScaleRequest>& scale_req_b,
        hls::stream<cnn_v10::ScaleResponse>& scale_rsp_b,
        hls::stream<cnn_v10::ScaleCredit>& scale_ret_b,
        unsigned c,unsigned w,unsigned blocks,unsigned slot_words,
        unsigned transition_stage,
        volatile ap_uint<32>& trace_a,volatile ap_uint<32>& trace_b) {
    ParamReader params(commands,responses);
    ParamReader residual_a(residual_commands_a,residual_responses_a);
    ParamReader residual_b(residual_commands_b,residual_responses_b);
    DdrWriter writer_a(write_commands_a,write_data_a,write_committed_a);
    DdrWriter writer_b(write_commands_b,write_data_b,write_committed_b);
    cnn_v10::ScaleClient scale_a(scale_req_a,scale_rsp_a,scale_ret_a);
    cnn_v10::ScaleClient scale_b(scale_req_b,scale_rsp_b,scale_ret_b);
    if(transition_stage) {
        const unsigned output_base=transition_stage==1?slot_words:0;
        n1_output_dual(in_a,writer_a,row_ready_a,in_b,writer_b,row_ready_b,
                       output_base,transition_stage==2,trace_a,trace_b);
        params.finish(); residual_a.finish(); residual_b.finish();
        writer_a.finish(); writer_b.finish(); scale_a.finish(); scale_b.finish();
        trace_a=0; trace_b=0; return;
    }
    // HLS007/008 discarded core A's address when both dataflow children read
    // one coefficient pointer, even with a T2P binding.  Parameters are still
    // fetched once; broadcast the small coefficient cache so each child owns
    // one unambiguous memory interface.  The large shared GELU stays single.
    static coeff co_a[256],co_b[256];
    static ap_int<32> sm[256];
    static ap_uint<6> ss[256];
#pragma HLS BIND_STORAGE variable=co_a type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=co_b type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=sm type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=ss type=ram_2p impl=lutram
    trace_a=0; trace_b=0;
    unsigned base=0;
    for(unsigned n=0;n<blocks;++n) {
        ap_int<32> rm; ap_uint<6> rs;
        load_coeff(params,base,c,5*c,c,co_a);
        for(unsigned ch=0;ch<c;++ch) {
#pragma HLS PIPELINE II=1
            co_b[ch]=co_a[ch];
        }
        load_residual(params,base,c,sm,ss,rm,rs);
        pointwise_final_dual(in_a,wt_a,residual_a,residual_ready_a,residual_release_a,
                             writer_a,row_ready_a,scale_a,
                             in_b,wt_b,residual_b,residual_ready_b,residual_release_b,
                             writer_b,row_ready_b,scale_b,c,w,co_a,co_b,sm,ss,rm,rs,n,
                             slot_words,trace_a,trace_b);
        base+=cnn_v10_stride(c);
    }
    params.finish(); residual_a.finish(); residual_b.finish();
    writer_a.finish(); writer_b.finish(); scale_a.finish(); scale_b.finish();
    trace_a=0; trace_b=0;
}

static void collect_errors(hls::stream<unsigned>& a,hls::stream<unsigned>& b,
                           unsigned& error) {
    error=a.read()|b.read();
}

static void chain(const ap_uint<128>* p1,const ap_uint<128>* p2,
                  const ap_uint<128>* ar_a,hls::burst_maxi<ap_uint<128> > aw_a,
                  const ap_uint<128>* ar_b,hls::burst_maxi<ap_uint<128> > aw_b,
                  unsigned c,unsigned w,unsigned blocks,unsigned slot_words,unsigned profile,
                  unsigned transition_stage,
                  unsigned& error,
                  volatile ap_uint<32>& tf_a,volatile ap_uint<32>& td3_a,
                  volatile ap_uint<32>& td7_a,volatile ap_uint<32>& tp1_a,
                  volatile ap_uint<32>& tp2_a,volatile ap_uint<32>& tw_a,
                  volatile ap_uint<32>& tf_b,volatile ap_uint<32>& td3_b,
                  volatile ap_uint<32>& td7_b,volatile ap_uint<32>& tp1_b,
                  volatile ap_uint<32>& tp2_b,volatile ap_uint<32>& tw_b) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    // Only the external feed/final-result paths and residual path use DDR.
    // The q3/q7/expanded stage boundaries are bounded on-chip BRAM FIFOs.
    hls::stream<ReadCmd> p1_cmd[4],p2_cmd[2],a_read_cmd[2],b_read_cmd[2];
    hls::stream<ap_uint<128> > p1_data[4],p2_data[2],a_read_data[2],b_read_data[2];
    hls::stream<WriteCmd> a_write_cmd[2],b_write_cmd[2];
    hls::stream<ap_uint<128> > a_write_data[2],b_write_data[2];
    hls::stream<ap_uint<1> > a_committed[2],b_committed[2];
#pragma HLS ARRAY_PARTITION variable=p1_cmd complete
#pragma HLS ARRAY_PARTITION variable=p2_cmd complete
#pragma HLS ARRAY_PARTITION variable=a_read_cmd complete
#pragma HLS ARRAY_PARTITION variable=b_read_cmd complete
#pragma HLS ARRAY_PARTITION variable=p1_data complete
#pragma HLS ARRAY_PARTITION variable=p2_data complete
#pragma HLS ARRAY_PARTITION variable=a_read_data complete
#pragma HLS ARRAY_PARTITION variable=b_read_data complete
#pragma HLS ARRAY_PARTITION variable=a_write_cmd complete
#pragma HLS ARRAY_PARTITION variable=b_write_cmd complete
#pragma HLS ARRAY_PARTITION variable=a_write_data complete
#pragma HLS ARRAY_PARTITION variable=b_write_data complete
#pragma HLS ARRAY_PARTITION variable=a_committed complete
#pragma HLS ARRAY_PARTITION variable=b_committed complete
#pragma HLS STREAM variable=p1_cmd depth=2
#pragma HLS STREAM variable=p2_cmd depth=2
#pragma HLS STREAM variable=a_read_cmd depth=2
#pragma HLS STREAM variable=b_read_cmd depth=2
#pragma HLS STREAM variable=p1_data depth=32
#pragma HLS STREAM variable=p2_data depth=32
#pragma HLS STREAM variable=a_read_data depth=32
#pragma HLS STREAM variable=b_read_data depth=32
#pragma HLS STREAM variable=a_write_cmd depth=2
#pragma HLS STREAM variable=b_write_cmd depth=2
#pragma HLS STREAM variable=a_write_data depth=32
#pragma HLS STREAM variable=b_write_data depth=32
#pragma HLS STREAM variable=a_committed depth=2
#pragma HLS STREAM variable=b_committed depth=2
#pragma HLS BIND_STORAGE variable=p1_data type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=p2_data type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=a_read_data type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=b_read_data type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=a_write_data type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=b_write_data type=fifo impl=lutram

    hls::stream<cnn_v10::ScaleRequest> scale_req_a[3],scale_req_b[3];
    hls::stream<cnn_v10::ScaleResponse> scale_rsp_a[3],scale_rsp_b[3];
    hls::stream<cnn_v10::ScaleCredit> scale_ret_a[3],scale_ret_b[3];
#pragma HLS ARRAY_PARTITION variable=scale_req_a complete
#pragma HLS ARRAY_PARTITION variable=scale_req_b complete
#pragma HLS ARRAY_PARTITION variable=scale_rsp_a complete
#pragma HLS ARRAY_PARTITION variable=scale_rsp_b complete
#pragma HLS ARRAY_PARTITION variable=scale_ret_a complete
#pragma HLS ARRAY_PARTITION variable=scale_ret_b complete
#pragma HLS STREAM variable=scale_req_a depth=16
#pragma HLS STREAM variable=scale_req_b depth=16
#pragma HLS STREAM variable=scale_rsp_a depth=16
#pragma HLS STREAM variable=scale_rsp_b depth=16
#pragma HLS STREAM variable=scale_ret_a depth=16
#pragma HLS STREAM variable=scale_ret_b depth=16
#pragma HLS BIND_STORAGE variable=scale_req_a type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=scale_req_b type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=scale_rsp_a type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=scale_rsp_b type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=scale_ret_a type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=scale_ret_b type=fifo impl=lutram

    hls::stream<pixel> input_a("input_a"),q3_a("q3_a"),q7_a("q7_a"),
        res_a("res_a"),expanded_a("expanded_a");
    hls::stream<pixel> input_b("input_b"),q3_b("q3_b"),q7_b("q7_b"),
        res_b("res_b"),expanded_b("expanded_b");
    hls::stream<pixel> unused_a("unused_a"),unused_b("unused_b");
    hls::stream<tile> wt1_a("wt1_a"),wt1_b("wt1_b"),
        wt2_a("wt2_a"),wt2_b("wt2_b");
    hls::stream<cnn_v10::RowReadyToken> row_ready_a("row_ready_a"),
        row_ready_b("row_ready_b");
    hls::stream<ap_uint<32> > residual_ready_a("residual_ready_a"),
        residual_ready_b("residual_ready_b");
    hls::stream<ap_uint<1> > residual_release_a("residual_release_a"),
        residual_release_b("residual_release_b");
    hls::stream<unsigned> errors_a("errors_a"),errors_b("errors_b");
#pragma HLS STREAM variable=input_a depth=32
#pragma HLS STREAM variable=input_b depth=32
#pragma HLS STREAM variable=q3_a depth=4096
#pragma HLS STREAM variable=q3_b depth=4096
#pragma HLS STREAM variable=q7_a depth=8192
#pragma HLS STREAM variable=q7_b depth=8192
#pragma HLS STREAM variable=res_a depth=64
#pragma HLS STREAM variable=res_b depth=64
#pragma HLS STREAM variable=expanded_a depth=2048
#pragma HLS STREAM variable=expanded_b depth=2048
#pragma HLS STREAM variable=wt1_a depth=2
#pragma HLS STREAM variable=wt1_b depth=2
#pragma HLS STREAM variable=wt2_a depth=2
#pragma HLS STREAM variable=wt2_b depth=2
#pragma HLS STREAM variable=row_ready_a depth=64
#pragma HLS STREAM variable=row_ready_b depth=64
#pragma HLS STREAM variable=residual_ready_a depth=4
#pragma HLS STREAM variable=residual_ready_b depth=4
#pragma HLS STREAM variable=residual_release_a depth=4
#pragma HLS STREAM variable=residual_release_b depth=4
#pragma HLS STREAM variable=errors_a depth=2
#pragma HLS STREAM variable=errors_b depth=2
#pragma HLS BIND_STORAGE variable=q3_a type=fifo impl=bram
#pragma HLS BIND_STORAGE variable=q3_b type=fifo impl=bram
#pragma HLS BIND_STORAGE variable=q7_a type=fifo impl=bram
#pragma HLS BIND_STORAGE variable=q7_b type=fifo impl=bram
#pragma HLS BIND_STORAGE variable=res_a type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=res_b type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=expanded_a type=fifo impl=bram
#pragma HLS BIND_STORAGE variable=expanded_b type=fifo impl=bram
#pragma HLS BIND_STORAGE variable=wt1_a type=fifo impl=lutram
#pragma HLS BIND_STORAGE variable=wt1_b type=fifo impl=lutram

#define CNN_V10_CALLS \
    cnn_v10::param_broker<4>(p1,p1_cmd,p1_data); \
    cnn_v10::param_broker<2>(p2,p2_cmd,p2_data); \
    cnn_v10::param_broker<2>(ar_a,a_read_cmd,a_read_data); \
    cnn_v10::param_broker<2>(ar_b,b_read_cmd,b_read_data); \
    cnn_v10::write_broker<2>(aw_a,a_write_cmd,a_write_data,a_committed); \
    cnn_v10::write_broker<2>(aw_b,b_write_cmd,b_write_data,b_committed); \
    cnn_v10::scale_service<0,3,16>(scale_req_a,scale_rsp_a,scale_ret_a); \
    cnn_v10::scale_service<1,3,16>(scale_req_b,scale_rsp_b,scale_ret_b)

#ifdef __SYNTHESIS__
    CNN_V10_CALLS;
    feed_chain(a_read_cmd[0],a_read_data[0],slot_words,w,blocks,
               transition_stage,row_ready_a,input_a,tf_a,errors_a);
    feed_chain(b_read_cmd[0],b_read_data[0],slot_words,w,blocks,
               transition_stage,row_ready_b,input_b,tf_b,errors_b);
    depthwise_chain<3,4,false,0>(p1_cmd[0],p1_data[0],input_a,q3_a,unused_a,
        input_b,q3_b,unused_b,scale_req_a[0],scale_rsp_a[0],scale_ret_a[0],
        scale_req_b[0],scale_rsp_b[0],scale_ret_b[0],c,w,blocks,
        transition_stage,td3_a,td3_b);
    depthwise_chain<7,16,true,1>(p1_cmd[1],p1_data[1],q3_a,q7_a,res_a,
        q3_b,q7_b,res_b,scale_req_a[1],scale_rsp_a[1],scale_ret_a[1],
        scale_req_b[1],scale_rsp_b[1],scale_ret_b[1],c,w,blocks,
        transition_stage,td7_a,td7_b);
    residual_writer(res_a,a_write_cmd[0],a_write_data[0],a_committed[0],
        residual_ready_a,residual_release_a,slot_words,w,blocks,transition_stage,tw_a);
    residual_writer(res_b,b_write_cmd[0],b_write_data[0],b_committed[0],
        residual_ready_b,residual_release_b,slot_words,w,blocks,transition_stage,tw_b);
    weight_broadcast(p1_cmd[3],p1_data[3],wt1_a,wt1_b,c,w,blocks,false,
                     transition_stage);
    pointwise1_chain(p1_cmd[2],p1_data[2],q7_a,wt1_a,expanded_a,q7_b,wt1_b,
                     expanded_b,c,w,blocks,profile,transition_stage,tp1_a,tp1_b);
    weight_broadcast(p2_cmd[1],p2_data[1],wt2_a,wt2_b,c,w,blocks,true,
                     transition_stage);
    pointwise2_chain(p2_cmd[0],p2_data[0],expanded_a,wt2_a,
        a_read_cmd[1],a_read_data[1],residual_ready_a,residual_release_a,
        a_write_cmd[1],a_write_data[1],a_committed[1],row_ready_a,
        scale_req_a[2],scale_rsp_a[2],scale_ret_a[2],expanded_b,wt2_b,
        b_read_cmd[1],b_read_data[1],residual_ready_b,residual_release_b,
        b_write_cmd[1],b_write_data[1],b_committed[1],row_ready_b,
        scale_req_b[2],scale_rsp_b[2],scale_ret_b[2],c,w,blocks,slot_words,
        transition_stage,tp2_a,tp2_b);
    collect_errors(errors_a,errors_b,error);
#else
    NativeTaskBatch tasks(18);
    std::thread t0([&]{NativeTaskExit d(tasks);cnn_v10::param_broker<4>(p1,p1_cmd,p1_data);});
    std::thread t1([&]{NativeTaskExit d(tasks);cnn_v10::param_broker<2>(p2,p2_cmd,p2_data);});
    std::thread t2([&]{NativeTaskExit d(tasks);cnn_v10::param_broker<2>(ar_a,a_read_cmd,a_read_data);});
    std::thread t3([&]{NativeTaskExit d(tasks);cnn_v10::param_broker<2>(ar_b,b_read_cmd,b_read_data);});
    std::thread t4([&]{NativeTaskExit d(tasks);cnn_v10::write_broker<2>(aw_a,a_write_cmd,a_write_data,a_committed);});
    std::thread t5([&]{NativeTaskExit d(tasks);cnn_v10::write_broker<2>(aw_b,b_write_cmd,b_write_data,b_committed);});
    std::thread t6([&]{NativeTaskExit d(tasks);cnn_v10::scale_service<0,3,16>(scale_req_a,scale_rsp_a,scale_ret_a);});
    std::thread t7([&]{NativeTaskExit d(tasks);cnn_v10::scale_service<1,3,16>(scale_req_b,scale_rsp_b,scale_ret_b);});
    std::thread t8([&]{NativeTaskExit d(tasks);feed_chain(a_read_cmd[0],a_read_data[0],slot_words,w,blocks,transition_stage,row_ready_a,input_a,tf_a,errors_a);});
    std::thread t9([&]{NativeTaskExit d(tasks);feed_chain(b_read_cmd[0],b_read_data[0],slot_words,w,blocks,transition_stage,row_ready_b,input_b,tf_b,errors_b);});
    std::thread t10([&]{NativeTaskExit d(tasks);depthwise_chain<3,4,false,0>(p1_cmd[0],p1_data[0],input_a,q3_a,unused_a,input_b,q3_b,unused_b,scale_req_a[0],scale_rsp_a[0],scale_ret_a[0],scale_req_b[0],scale_rsp_b[0],scale_ret_b[0],c,w,blocks,transition_stage,td3_a,td3_b);});
    std::thread t11([&]{NativeTaskExit d(tasks);depthwise_chain<7,16,true,1>(p1_cmd[1],p1_data[1],q3_a,q7_a,res_a,q3_b,q7_b,res_b,scale_req_a[1],scale_rsp_a[1],scale_ret_a[1],scale_req_b[1],scale_rsp_b[1],scale_ret_b[1],c,w,blocks,transition_stage,td7_a,td7_b);});
    std::thread t12([&]{NativeTaskExit d(tasks);residual_writer(res_a,a_write_cmd[0],a_write_data[0],a_committed[0],residual_ready_a,residual_release_a,slot_words,w,blocks,transition_stage,tw_a);});
    std::thread t13([&]{NativeTaskExit d(tasks);residual_writer(res_b,b_write_cmd[0],b_write_data[0],b_committed[0],residual_ready_b,residual_release_b,slot_words,w,blocks,transition_stage,tw_b);});
    std::thread t14([&]{NativeTaskExit d(tasks);weight_broadcast(p1_cmd[3],p1_data[3],wt1_a,wt1_b,c,w,blocks,false,transition_stage);});
    std::thread t15([&]{NativeTaskExit d(tasks);pointwise1_chain(p1_cmd[2],p1_data[2],q7_a,wt1_a,expanded_a,q7_b,wt1_b,expanded_b,c,w,blocks,profile,transition_stage,tp1_a,tp1_b);});
    std::thread t16([&]{NativeTaskExit d(tasks);weight_broadcast(p2_cmd[1],p2_data[1],wt2_a,wt2_b,c,w,blocks,true,transition_stage);});
    std::thread t17([&]{NativeTaskExit d(tasks);pointwise2_chain(p2_cmd[0],p2_data[0],expanded_a,wt2_a,a_read_cmd[1],a_read_data[1],residual_ready_a,residual_release_a,a_write_cmd[1],a_write_data[1],a_committed[1],row_ready_a,scale_req_a[2],scale_rsp_a[2],scale_ret_a[2],expanded_b,wt2_b,b_read_cmd[1],b_read_data[1],residual_ready_b,residual_release_b,b_write_cmd[1],b_write_data[1],b_committed[1],row_ready_b,scale_req_b[2],scale_rsp_b[2],scale_ret_b[2],c,w,blocks,slot_words,transition_stage,tp2_a,tp2_b);});
    collect_errors(errors_a,errors_b,error);
    t0.join();t1.join();t2.join();t3.join();t4.join();t5.join();t6.join();t7.join();t8.join();
    t9.join();t10.join();t11.join();t12.join();t13.join();t14.join();t15.join();t16.join();t17.join();
#endif
#undef CNN_V10_CALLS
}

} // namespace

void cnn_pipeline_v10(const ap_uint<128>* params_pw1,
                      const ap_uint<128>* params_pw2,
                      const ap_uint<128>* activation_a_rd,
                      hls::burst_maxi<ap_uint<128> > activation_a_wr,
                      const ap_uint<128>* activation_b_rd,
                      hls::burst_maxi<ap_uint<128> > activation_b_wr,
                      unsigned profile,unsigned block_count,
                      unsigned params_words,unsigned slot_words,
                      unsigned arena_words,unsigned flags,
                      unsigned& protocol_error,
                      volatile ap_uint<32>& trace_a_feed,
                      volatile ap_uint<32>& trace_a_dw3,
                      volatile ap_uint<32>& trace_a_dw7,
                      volatile ap_uint<32>& trace_a_pw1,
                      volatile ap_uint<32>& trace_a_pw2,
                      volatile ap_uint<32>& trace_a_write,
                      volatile ap_uint<32>& trace_b_feed,
                      volatile ap_uint<32>& trace_b_dw3,
                      volatile ap_uint<32>& trace_b_dw7,
                      volatile ap_uint<32>& trace_b_pw1,
                      volatile ap_uint<32>& trace_b_pw2,
                      volatile ap_uint<32>& trace_b_write) {
#pragma HLS INTERFACE mode=m_axi port=params_pw1 bundle=g_param1 offset=slave max_read_burst_length=32 num_read_outstanding=4 max_widen_bitwidth=128
#pragma HLS INTERFACE mode=m_axi port=params_pw2 bundle=g_param2 offset=slave max_read_burst_length=32 num_read_outstanding=4 max_widen_bitwidth=128
#pragma HLS INTERFACE mode=m_axi port=activation_a_rd bundle=g_act_a_r offset=slave max_read_burst_length=32 num_read_outstanding=4 max_widen_bitwidth=128
#pragma HLS INTERFACE mode=m_axi port=activation_a_wr bundle=g_act_a_w offset=slave max_write_burst_length=32 num_write_outstanding=4 max_widen_bitwidth=128
#pragma HLS INTERFACE mode=m_axi port=activation_b_rd bundle=g_act_b_r offset=slave max_read_burst_length=32 num_read_outstanding=4 max_widen_bitwidth=128
#pragma HLS INTERFACE mode=m_axi port=activation_b_wr bundle=g_act_b_w offset=slave max_write_burst_length=32 num_write_outstanding=4 max_widen_bitwidth=128
#pragma HLS INTERFACE mode=s_axilite port=params_pw1 bundle=control
#pragma HLS INTERFACE mode=s_axilite port=params_pw2 bundle=control
#pragma HLS INTERFACE mode=s_axilite port=activation_a_rd bundle=control
#pragma HLS INTERFACE mode=s_axilite port=activation_a_wr bundle=control
#pragma HLS INTERFACE mode=s_axilite port=activation_b_rd bundle=control
#pragma HLS INTERFACE mode=s_axilite port=activation_b_wr bundle=control
#pragma HLS INTERFACE mode=s_axilite port=profile bundle=control
#pragma HLS INTERFACE mode=s_axilite port=block_count bundle=control
#pragma HLS INTERFACE mode=s_axilite port=params_words bundle=control
#pragma HLS INTERFACE mode=s_axilite port=slot_words bundle=control
#pragma HLS INTERFACE mode=s_axilite port=arena_words bundle=control
#pragma HLS INTERFACE mode=s_axilite port=flags bundle=control
#pragma HLS INTERFACE mode=ap_vld port=protocol_error
#pragma HLS INTERFACE mode=ap_none port=trace_a_feed
#pragma HLS INTERFACE mode=ap_none port=trace_a_dw3
#pragma HLS INTERFACE mode=ap_none port=trace_a_dw7
#pragma HLS INTERFACE mode=ap_none port=trace_a_pw1
#pragma HLS INTERFACE mode=ap_none port=trace_a_pw2
#pragma HLS INTERFACE mode=ap_none port=trace_a_write
#pragma HLS INTERFACE mode=ap_none port=trace_b_feed
#pragma HLS INTERFACE mode=ap_none port=trace_b_dw3
#pragma HLS INTERFACE mode=ap_none port=trace_b_dw7
#pragma HLS INTERFACE mode=ap_none port=trace_b_pw1
#pragma HLS INTERFACE mode=ap_none port=trace_b_pw2
#pragma HLS INTERFACE mode=ap_none port=trace_b_write
#pragma HLS INTERFACE mode=ap_ctrl_hs port=return
    protocol_error=0;
    trace_a_feed=0;trace_a_dw3=0;trace_a_dw7=0;trace_a_pw1=0;trace_a_pw2=0;trace_a_write=0;
    trace_b_feed=0;trace_b_dw3=0;trace_b_dw7=0;trace_b_pw1=0;trace_b_pw2=0;trace_b_write=0;
    if(profile>3 || flags || !block_count || block_count>cnn_v10_max_blocks(profile)) {
        protocol_error=1; return;
    }
    const unsigned c=cnn_v10_channels(profile),w=cnn_v10_width(profile);
    unsigned expected_words=profile==cnn_v10::kN1Profile?
        cnn_v10::kN1ParamWords:0;
    for(unsigned n=0;n<block_count && profile!=cnn_v10::kN1Profile;++n) {
#pragma HLS PIPELINE II=1
        expected_words+=cnn_v10_stride(c);
    }
    if(params_words!=expected_words || slot_words!=cnn_v10_slot_words(profile) ||
       arena_words!=cnn_v10_arena_words(profile)) {
        protocol_error=1; return;
    }
    const bool valid_params=profile==cnn_v10::kN1Profile?
        valid_n1_params(params_pw1):
        (valid_metadata(params_pw1,c,block_count) &&
         valid_metadata(params_pw2,c,block_count) &&
         valid_gelu_padding(params_pw1,c,block_count,profile));
    if(!valid_params) {
        protocol_error=2; return;
    }
    // Keep one syntactic chain call site for both the normal profiles and the
    // two sequential P3 stages.  This makes reuse of the existing DW/PW MAC
    // hierarchy explicit; HLS resource reports must still prove that the
    // runtime transition mode did not clone those operators.
    const bool transition=profile==cnn_v10::kN1Profile;
    const unsigned stages=transition?2:1;
    for(unsigned stage_index=0;stage_index<stages;++stage_index) {
        const unsigned stage=transition?stage_index+1:0;
        const unsigned stage_c=!transition?c:
            (stage==1?cnn_v10::kN1InputChannels:cnn_v10::kN1OutputChannels);
        const unsigned stage_w=!transition?w:
            (stage==1?cnn_v10::kN1InputWidth:cnn_v10::kN1OutputWidth);
        const unsigned stage_blocks=transition?1:block_count;
        chain(params_pw1,params_pw2,activation_a_rd,activation_a_wr,
              activation_b_rd,activation_b_wr,stage_c,stage_w,stage_blocks,
              slot_words,profile,stage,protocol_error,trace_a_feed,trace_a_dw3,
              trace_a_dw7,trace_a_pw1,trace_a_pw2,trace_a_write,
              trace_b_feed,trace_b_dw3,trace_b_dw7,trace_b_pw1,
              trace_b_pw2,trace_b_write);
    }
}



