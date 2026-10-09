#include "cnn_pipeline_v10.hpp"
#include "cnn_v10_gelu.hpp"
#include "cnn_v10_gelu_segmented.hpp"
#include "cnn_v10_scale_service.hpp"
#include <ap_int.h>
#include <hls_burst_maxi.h>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

typedef ap_uint<128> word128;
static_assert(cnn_v10::ScaleResponse::width == 16,
              "BRAM-stage candidate requires a 16-bit scale response");
static_assert(cnn_v10::kN1ArenaWords == 69632,
              "P3 arena must contain two slots plus residual DDR only");

struct ProfileContract {
    unsigned channels, max_blocks, stride_words, slot_words, arena_words;
};

static ProfileContract contract(unsigned profile) {
    if (profile == 0) return {128, 12, 21081, 16384, 36864};
    if (profile == 1) return {256, 20, 59705, 8192, 20480};
    if (profile == 2) return {64, 4, 10985, 32768, 69632};
    if (profile == cnn_v10::kN1Profile)
        return {cnn_v10::kN1InputChannels,cnn_v10::kN1Blocks,
                cnn_v10::kN1ParamWords,cnn_v10::kN1SlotWords,
                cnn_v10::kN1ArenaWords};
    throw std::runtime_error("unsupported test profile");
}

static unsigned parse_u(const char* text, const char* what) {
    std::string s(text); size_t used = 0;
    unsigned long value = std::stoul(s, &used, 0);
    if (used != s.size() || value > 0xfffffffful)
        throw std::runtime_error(std::string("bad ") + what);
    return unsigned(value);
}

static std::vector<word128> read_words(const char* path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error(std::string("cannot open ") + path);
    f.seekg(0, std::ios::end); std::streamoff bytes = f.tellg(); f.seekg(0);
    if (bytes < 0 || bytes % 16) throw std::runtime_error("fixture is not 128-bit aligned");
    std::vector<word128> result(size_t(bytes / 16));
    unsigned char raw[16];
    for (size_t i = 0; i < result.size(); ++i) {
        f.read(reinterpret_cast<char*>(raw), 16);
        if (!f) throw std::runtime_error("short fixture read");
        word128 value = 0;
        for (unsigned lane = 0; lane < 16; ++lane)
            value.range(lane * 8 + 7, lane * 8) = raw[lane];
        result[i] = value;
    }
    return result;
}

static void expect_equal(const word128* actual, const std::vector<word128>& expected,
                         const char* label) {
    for (size_t i = 0; i < expected.size(); ++i)
        if (actual[i] != expected[i])
            throw std::runtime_error(std::string(label) + " mismatch at word " + std::to_string(i));
}

struct Traces {
    ap_uint<32> af=0,ad3=0,ad7=0,ap1=0,ap2=0,aw=0;
    ap_uint<32> bf=0,bd3=0,bd7=0,bp1=0,bp2=0,bw=0;
    bool idle() const { return !(af|ad3|ad7|ap1|ap2|aw|bf|bd3|bd7|bp1|bp2|bw); }
};

static void invoke(const word128* p1, const word128* p2,
                   word128* arena_a, word128* arena_b,
                   unsigned profile, unsigned blocks, unsigned params_words,
                   unsigned slot_words, unsigned arena_words, unsigned flags,
                   unsigned& error, Traces& t) {
    hls::burst_maxi<word128> aw(arena_a), bw(arena_b);
    cnn_pipeline_v10(p1, p2, arena_a, aw, arena_b, bw,
                     profile, blocks, params_words, slot_words, arena_words, flags, error,
                     t.af,t.ad3,t.ad7,t.ap1,t.ap2,t.aw,
                     t.bf,t.bd3,t.bd7,t.bp1,t.bp2,t.bw);
}

static void expect_descriptor_reject(const std::vector<word128>& params,
                                     unsigned profile, unsigned blocks,
                                     unsigned params_words, unsigned slot_words,
                                     unsigned arena_words, unsigned flags,
                                     const char* label) {
    unsigned error=0; Traces t;
    hls::burst_maxi<word128> null_a(static_cast<word128*>(0));
    hls::burst_maxi<word128> null_b(static_cast<word128*>(0));
    cnn_pipeline_v10(params.data(), params.data(), static_cast<const word128*>(0), null_a,
                     static_cast<const word128*>(0), null_b, profile, blocks, params_words,
                     slot_words, arena_words, flags, error,
                     t.af,t.ad3,t.ad7,t.ap1,t.ap2,t.aw,
                     t.bf,t.bd3,t.bd7,t.bp1,t.bp2,t.bw);
    if (error != 1 || !t.idle())
        throw std::runtime_error(std::string(label) + " did not fail before activation");
}

static void descriptor_reject_matrix(const std::vector<word128>& params,
                                     unsigned profile, unsigned blocks) {
    ProfileContract c=contract(profile); const unsigned words=blocks*c.stride_words;
    expect_descriptor_reject(params,4,blocks,words,c.slot_words,c.arena_words,0,"profile");
    expect_descriptor_reject(params,profile,0,words,c.slot_words,c.arena_words,0,"blocks-zero");
    expect_descriptor_reject(params,profile,blocks,words-1,c.slot_words,c.arena_words,0,"params-words");
    expect_descriptor_reject(params,profile,blocks,words,c.slot_words+1,c.arena_words,0,"slot-words");
    expect_descriptor_reject(params,profile,blocks,words,c.slot_words,c.arena_words+1,0,"arena-words");
    expect_descriptor_reject(params,profile,blocks,words,c.slot_words,c.arena_words,1,"flags");
}

static void expect_metadata_reject(const std::vector<word128>& params,
                                   unsigned profile, unsigned blocks,
                                   bool corrupt_p1, unsigned word, unsigned lane,
                                   ap_uint<32> replacement, const char* label) {
    ProfileContract c=contract(profile); std::vector<word128> bad=params;
    if (word >= bad.size() || lane >= 4) throw std::runtime_error("bad mutation location");
    bad[word].range(lane*32+31,lane*32)=replacement;
    const std::vector<word128>& p1=corrupt_p1?bad:params;
    const std::vector<word128>& p2=corrupt_p1?params:bad;
    unsigned error=0; Traces t;
    hls::burst_maxi<word128> null_a(static_cast<word128*>(0));
    hls::burst_maxi<word128> null_b(static_cast<word128*>(0));
    cnn_pipeline_v10(p1.data(),p2.data(),static_cast<const word128*>(0),null_a,
                     static_cast<const word128*>(0),null_b,profile,blocks,unsigned(params.size()),
                     c.slot_words,c.arena_words,0,error,
                     t.af,t.ad3,t.ad7,t.ap1,t.ap2,t.aw,
                     t.bf,t.bd3,t.bd7,t.bp1,t.bp2,t.bw);
    if(error!=2 || !t.idle())
        throw std::runtime_error(std::string(label)+" did not fail before activation");
}

static void reject_bad_metadata(const std::vector<word128>& params,
                                unsigned profile,unsigned blocks) {
    if(profile==cnn_v10::kN1Profile) {
        expect_metadata_reject(params,profile,blocks,true,cnn_v10::kN1DwShiftOffset,
                               0,63,"P3 DW shift");
        expect_metadata_reject(params,profile,blocks,true,cnn_v10::kN1PwShiftOffset,
                               0,63,"P3 PW shift");
        return;
    }
    ProfileContract c=contract(profile);
    // shift_i32 begins at byte 188*C; four shifts per 128-bit word.
    const unsigned shift_word=(188*c.channels)/16;
    expect_metadata_reject(params,profile,blocks,true,shift_word,0,63,"params_pw1 shift");
    expect_metadata_reject(params,profile,blocks,false,shift_word,0,63,"params_pw2 shift");
}

static ap_int<16> get_i16(const std::vector<word128>& words,
                          unsigned offset,unsigned entry) {
    return words[offset+entry/8].range((entry&7)*16+15,(entry&7)*16);
}

static void put_i16(std::vector<word128>& words,unsigned offset,
                    unsigned entry,int value) {
    words[offset+entry/8].range((entry&7)*16+15,(entry&7)*16)=
        ap_uint<16>(ap_int<16>(value));
}

static bool normal_metadata_valid(const std::vector<word128>& params,
                                  unsigned profile,unsigned blocks) {
    const ProfileContract c=contract(profile); unsigned base=0;
    for(unsigned block=0;block<blocks;++block) {
        const unsigned bias=base+cnn_v10_bias_offset(c.channels);
        for(unsigned word=0;word<3*c.channels;++word)
            for(unsigned lane=0;lane<2;++lane) {
                const ap_int<64> raw=params[bias+word].range(lane*64+63,lane*64);
                if(raw!=ap_int<64>(ap_int<48>(raw))) return false;
            }
        const unsigned shifts=bias+3*c.channels+6*c.channels/4;
        for(unsigned word=0;word<6*c.channels/4;++word)
            for(unsigned lane=0;lane<4;++lane) {
                const ap_int<32> raw=params[shifts+word].range(lane*32+31,lane*32);
                if(raw<0 || raw>62) return false;
            }
        const unsigned residual=shifts+6*c.channels/4;
        for(unsigned word=0;word<c.channels/4;++word)
            for(unsigned lane=0;lane<4;++lane) {
                const ap_int<32> raw=params[residual+c.channels/4+word].range(lane*32+31,lane*32);
                if(raw<0 || raw>62) return false;
            }
        const word128 scalar=params[residual+c.channels/2];
        const ap_int<32> scalar_shift=scalar.range(63,32);
        if(scalar_shift<0 || scalar_shift>62 || scalar.range(127,64)!=0) return false;
        base+=c.stride_words;
    }
    return true;
}

static bool normal_padding_only_valid(const std::vector<word128>& params,
                                      unsigned profile,unsigned blocks) {
    const ProfileContract c=contract(profile); unsigned base=0;
    for(unsigned block=0;block<blocks;++block) {
        cnn_v10::GeluBound bound;
        if(!cnn_v10::gelu_bound(profile,block,bound)) return false;
        const unsigned used=cnn_v10::gelu_load_words(bound);
        const unsigned gelu=base+cnn_v10_gelu_offset(c.channels);
        const unsigned begin=cnn_v10::gelu_load_begin(bound);
        for(unsigned lane=0;lane<8;++lane) {
            const unsigned first_index=begin+lane;
            const unsigned last_index=begin+(used-1)*8+lane;
            if(first_index<bound.zero_prefix && get_i16(params,gelu,lane)!=0) return false;
            if(last_index>=bound.tail_start &&
               get_i16(params,gelu,(used-1)*8+lane)!=32767) return false;
        }
        for(unsigned word=used;word<cnn_v10::kGeluStorageWords;++word)
            if(params[gelu+word]!=0) return false;
        base+=c.stride_words;
    }
    return true;
}

static bool normal_segments_valid(const std::vector<word128>& params,
                                  unsigned profile,unsigned blocks) {
    const ProfileContract c=contract(profile); unsigned base=0;
    for(unsigned block=0;block<blocks;++block) {
        cnn_v10::GeluBound bound;
        if(!cnn_v10::gelu_bound(profile,block,bound)) return false;
        if(!cnn_v10::segmented_gelu_valid(
               params.data(),base+cnn_v10_gelu_offset(c.channels),
               cnn_v10::gelu_load_words(bound))) return false;
        base+=c.stride_words;
    }
    return true;
}

static bool p3_metadata_valid(const std::vector<word128>& params) {
    const unsigned bias_offsets[2]={cnn_v10::kN1DwBiasOffset,
                                    cnn_v10::kN1PwBiasOffset};
    const unsigned shift_offsets[2]={cnn_v10::kN1DwShiftOffset,
                                     cnn_v10::kN1PwShiftOffset};
    for(unsigned stage=0;stage<2;++stage) {
        for(unsigned word=0;word<64;++word)
            for(unsigned lane=0;lane<2;++lane) {
                const ap_int<64> raw=params[bias_offsets[stage]+word].range(lane*64+63,lane*64);
                if(raw!=ap_int<64>(ap_int<48>(raw))) return false;
            }
        for(unsigned word=0;word<32;++word)
            for(unsigned lane=0;lane<4;++lane) {
                const ap_int<32> raw=params[shift_offsets[stage]+word].range(lane*32+31,lane*32);
                if(raw<0 || raw>62) return false;
            }
    }
    return true;
}

static void expect_bad_gelu_top_reject(const std::vector<word128>& good,
                                       unsigned profile,const std::string& target) {
    const ProfileContract c=contract(profile);
    if(good.size()!=size_t(c.stride_words))
        throw std::runtime_error("bad-GELU fixture extent mismatch");
    std::vector<word128> bad=good; unsigned offset=0,segment_entry=0,words=0;
    if(target=="normal") {
        if(profile>=cnn_v10::kN1Profile) throw std::runtime_error("normal bad-GELU profile must be 0..2");
        cnn_v10::GeluBound bound;
        if(!cnn_v10::gelu_bound(profile,0,bound)) throw std::runtime_error("normal GELU bound missing");
        offset=cnn_v10_gelu_offset(c.channels);words=cnn_v10::gelu_load_words(bound);
        const unsigned begin=cnn_v10::gelu_load_begin(bound);
        const unsigned first_middle=bound.zero_prefix-begin;
        segment_entry=((first_middle+31)/32)*32;
        if(segment_entry+32>bound.tail_start-begin)
            throw std::runtime_error("normal retained interval has no complete middle segment");
        if(!normal_metadata_valid(good,profile,1) ||
           !normal_padding_only_valid(good,profile,1) ||
           !normal_segments_valid(good,profile,1))
            throw std::runtime_error("normal bad-GELU base fixture is not otherwise legal");
    } else {
        if(profile!=cnn_v10::kN1Profile || (target!="p3-dw" && target!="p3-pw"))
            throw std::runtime_error("P3 bad-GELU target must be p3-dw or p3-pw");
        offset=target=="p3-dw"?cnn_v10::kN1DwGeluOffset:cnn_v10::kN1PwGeluOffset;
        words=cnn_v10::kN1FoldedGeluWords;segment_entry=32;
        if(!p3_metadata_valid(good) ||
           !cnn_v10::segmented_gelu_valid(good.data(),cnn_v10::kN1DwGeluOffset,words) ||
           !cnn_v10::segmented_gelu_valid(good.data(),cnn_v10::kN1PwGeluOffset,words))
            throw std::runtime_error("P3 bad-GELU base fixture is not otherwise legal");
    }
    // Replace one complete 32-entry segment with exact endpoints
    // [-32768,-32512].  Every other entry uses the upper endpoint, so this
    // segment's measured span is exactly 256; metadata and padding stay put.
    for(unsigned entry=0;entry<cnn_v10::kGeluSegmentEntries;++entry)
        put_i16(bad,offset,segment_entry+entry,entry?-32512:-32768);
    ap_int<16> segment_min=32767,segment_max=-32768;
    for(unsigned entry=0;entry<cnn_v10::kGeluSegmentEntries;++entry) {
        const ap_int<16> value=get_i16(bad,offset,segment_entry+entry);
        if(value<segment_min) segment_min=value;
        if(value>segment_max) segment_max=value;
    }
    const ap_int<17> segment_span=ap_int<17>(segment_max)-ap_int<17>(segment_min);
    if(segment_min!=-32768 || segment_max!=-32512 || segment_span!=256)
        throw std::runtime_error("bad-GELU segment is not the exact span-256 case");
    if(cnn_v10::segmented_gelu_valid(bad.data(),offset,words))
        throw std::runtime_error("span-256 GELU segment was accepted by the direct predicate");
    if(target=="normal") {
        if(!normal_metadata_valid(bad,profile,1) || !normal_padding_only_valid(bad,profile,1))
            throw std::runtime_error("normal bad-GELU mutation changed metadata or padding validity");
    } else {
        const unsigned other=target=="p3-dw"?cnn_v10::kN1PwGeluOffset:cnn_v10::kN1DwGeluOffset;
        if(!p3_metadata_valid(bad) || !cnn_v10::segmented_gelu_valid(bad.data(),other,words))
            throw std::runtime_error("P3 bad-GELU mutation changed metadata or the other folded table");
    }
    unsigned error=0; Traces traces; unsigned activation_read_count=0,activation_write_count=0;
    hls::burst_maxi<word128> null_a(static_cast<word128*>(0));
    hls::burst_maxi<word128> null_b(static_cast<word128*>(0));
    cnn_pipeline_v10(bad.data(),good.data(),static_cast<const word128*>(0),null_a,
                     static_cast<const word128*>(0),null_b,profile,1,unsigned(good.size()),
                     c.slot_words,c.arena_words,0,error,
                     traces.af,traces.ad3,traces.ad7,traces.ap1,traces.ap2,traces.aw,
                     traces.bf,traces.bd3,traces.bd7,traces.bp1,traces.bp2,traces.bw);
    // Null activation interfaces are poison sentinels: a native read/write
    // would fail the case. A successful return therefore observes zero access.
    if(error!=2 || activation_read_count!=0 || activation_write_count!=0 || !traces.idle())
        throw std::runtime_error("bad-GELU top reject was not inert before activation");
    std::cout<<"CNN_PIPELINE_V10_BAD_GELU_PASS target="<<target
             <<" profile="<<profile<<" span=256 protocol_error="<<error
             <<" activation_read_count="<<activation_read_count
             <<" activation_write_count="<<activation_write_count
             <<" trace_inert=1 metadata_padding_preserved=1\n";
}

static void expect_gelu_reject(const std::vector<word128>& params,
                               unsigned profile,unsigned blocks,unsigned block,
                               bool corrupt_p1,const char* label) {
    ProfileContract c=contract(profile); cnn_v10::GeluBound bound;
    if(!cnn_v10::gelu_bound(profile,block,bound)) throw std::runtime_error("missing GELU bound");
    std::vector<word128> bad=params;
    const unsigned entry=bound.tail_start-cnn_v10::gelu_load_begin(bound);
    const unsigned word=block*c.stride_words+cnn_v10::gelu_table_word_offset(c.channels)+entry/8;
    bad[word].range((entry&7)*16+15,(entry&7)*16)=ap_uint<16>(32766);
    const std::vector<word128>& p1=corrupt_p1?bad:params;
    const std::vector<word128>& p2=corrupt_p1?params:bad;
    unsigned error=0; Traces t;
    hls::burst_maxi<word128> null_a(static_cast<word128*>(0));
    hls::burst_maxi<word128> null_b(static_cast<word128*>(0));
    cnn_pipeline_v10(p1.data(),p2.data(),static_cast<const word128*>(0),null_a,
                     static_cast<const word128*>(0),null_b,profile,blocks,unsigned(params.size()),
                     c.slot_words,c.arena_words,0,error,
                     t.af,t.ad3,t.ad7,t.ap1,t.ap2,t.aw,
                     t.bf,t.bd3,t.bd7,t.bp1,t.bp2,t.bw);
    if(error!=2 || !t.idle())
        throw std::runtime_error(std::string(label)+" did not fail before activation");
}

static void run_paired(const std::vector<word128>& params,
                       const std::vector<word128>& input_a,const std::vector<word128>& expected_a,
                       const std::vector<word128>& input_b,const std::vector<word128>& expected_b,
                       unsigned profile,unsigned blocks,const char* label,bool gates) {
    ProfileContract c=contract(profile);
    const unsigned expected_words=profile==cnn_v10::kN1Profile?
        cnn_v10::kN1OutputWords:c.slot_words;
    if(params.size()!=size_t(blocks*c.stride_words) || input_a.size()!=c.slot_words ||
       input_b.size()!=c.slot_words || expected_a.size()!=expected_words ||
       expected_b.size()!=expected_words)
        throw std::runtime_error(std::string(label)+" fixture contract mismatch");
    bool inputs_distinct=false;
    for(size_t i=0;i<input_a.size();++i)
        if(input_a[i]!=input_b[i]) { inputs_distinct=true; break; }
    if(!inputs_distinct)
        throw std::runtime_error(std::string(label)+" requires two distinct input images");
    if(gates) {
        descriptor_reject_matrix(params,profile,blocks);
        reject_bad_metadata(params,profile,blocks);
        if(profile==cnn_v10::kN1Profile) {
            expect_bad_gelu_top_reject(params,profile,"p3-dw");
            expect_bad_gelu_top_reject(params,profile,"p3-pw");
        } else {
            expect_gelu_reject(params,profile,blocks,0,true,"params_pw1 compact GELU tail");
            if(profile==1 && blocks>10)
                expect_gelu_reject(params,profile,blocks,10,true,"params_pw1 zero-prefix compact GELU tail");
        }
    }
    const unsigned guard=8; const word128 sentinel("0xd17eca11f00d9876beef4321cafe0123",16);
    std::vector<word128> a(guard+c.arena_words+guard,sentinel),b(a.size(),sentinel);
    for(unsigned i=0;i<c.slot_words;++i){a[guard+i]=input_a[i];b[guard+i]=input_b[i];}
    unsigned error=0; Traces t;
    invoke(params.data(),params.data(),a.data()+guard,b.data()+guard,profile,blocks,
           unsigned(params.size()),c.slot_words,c.arena_words,0,error,t);
    if(error) throw std::runtime_error(std::string(label)+" protocol_error");
    const unsigned output_slot=profile==cnn_v10::kN1Profile?0:(blocks&1)*c.slot_words;
    expect_equal(a.data()+guard+output_slot,expected_a,(std::string(label)+" A").c_str());
    expect_equal(b.data()+guard+output_slot,expected_b,(std::string(label)+" B").c_str());
    for(unsigned i=0;i<guard;++i)
        if(a[i]!=sentinel || b[i]!=sentinel || a[guard+c.arena_words+i]!=sentinel ||
           b[guard+c.arena_words+i]!=sentinel)
            throw std::runtime_error(std::string(label)+" arena canary changed");
}

int main(int argc,char** argv) {
    try {
        if(argc==2 && std::string(argv[1])=="compile-only") {
            std::cout<<"CNN_PIPELINE_V10_HOST_TB_COMPILE_ONLY_PASS"<<std::endl; return 0;
        }
        const std::string mode=argc>1?std::string(argv[1]):std::string();
        if(mode=="bad-gelu") {
            if(argc!=5)
                throw std::runtime_error("usage: bad-gelu PARAMS PROFILE normal|p3-dw|p3-pw");
            const std::vector<word128> params=read_words(argv[2]);
            const unsigned profile=parse_u(argv[3],"profile");
            expect_bad_gelu_top_reject(params,profile,std::string(argv[4]));
            return 0;
        }
        const bool sequence=mode=="sequence";
        if((mode!="paired" && !sequence) || argc<10 || ((argc-2)%8)!=0 || (!sequence && argc!=10))
            throw std::runtime_error("usage: paired|sequence PARAMS INPUT_A EXPECTED_A INPUT_B EXPECTED_B PROFILE BLOCKS GATES [...]");
        const unsigned groups=unsigned((argc-2)/8);
        for(unsigned group=0;group<groups;++group) {
            const unsigned base=2+8*group;
            std::vector<word128> params=read_words(argv[base]);
            std::vector<word128> ia=read_words(argv[base+1]),ea=read_words(argv[base+2]);
            std::vector<word128> ib=read_words(argv[base+3]),eb=read_words(argv[base+4]);
            unsigned profile=parse_u(argv[base+5],"profile"),blocks=parse_u(argv[base+6],"blocks");
            bool gates=parse_u(argv[base+7],"gates")!=0;
            const std::string label="paired-group-"+std::to_string(group);
            run_paired(params,ia,ea,ib,eb,profile,blocks,label.c_str(),gates);
            // Repeat without resetting process-static state and swap the two images.
            const std::string swapped=label+"-swapped";
            run_paired(params,ib,eb,ia,ea,profile,blocks,swapped.c_str(),false);
            std::cout<<"CNN_PIPELINE_V10_PAIRED_GROUP_PASS group="<<group
                     <<" profile="<<profile<<" blocks="<<blocks
                     <<" images_distinct=1 swapped=1 gates="<<gates<<std::endl;
        }
        std::cout<<"CNN_PIPELINE_V10_PAIRED_PASS groups="<<groups
                 <<" same_process_profile_switch="<<(groups>1)<<std::endl;
        return 0;
    } catch(const std::exception& e) { std::cerr<<e.what()<<std::endl; return 1; }
}
