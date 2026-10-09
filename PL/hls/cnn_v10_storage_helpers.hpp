#pragma once

#include <cstdint>

namespace cnn_v10_candidate {

struct Pw1PhysicalLocation {
    bool accepted;
    unsigned physical_bank;
    unsigned port;
    unsigned physical_address;
};

// One physical TDP bank contains two adjacent logical banks.  Each logical
// bank owns 2*BANK_DEPTH addresses (two image rows); therefore each physical
// bank has 4*BANK_DEPTH entries.
static inline Pw1PhysicalLocation pw1_physical_location(
        unsigned logical_bank,unsigned logical_address,
        unsigned logical_bank_depth) {
    Pw1PhysicalLocation result={false,0,0,0};
    if(logical_bank_depth==0 || logical_bank>=16 ||
       logical_address>=logical_bank_depth) return result;
    result.accepted=true;
    result.physical_bank=logical_bank>>1;
    result.port=logical_bank&1;
    result.physical_address=result.port*logical_bank_depth+logical_address;
    return result;
}

struct Dw7FixedRead {
    bool valid;
    unsigned physical_bank;
    unsigned address;
};

// base_x is aligned to 16 for both normal and P3.  safe_x is always legal,
// even for padding, so HLS may schedule an unconditional fixed-bank RAM read.
static inline Dw7FixedRead dw7_fixed_bank_read(
        unsigned input_width,unsigned channel,unsigned bank_shift,
        int input_y,int base_x,int dx,unsigned physical_bank) {
    Dw7FixedRead result={false,physical_bank,0};
    if(physical_bank>=16 || input_width==0) return result;
    const int within=(int(physical_bank)-dx)&15;
    const int source_x=base_x+within+dx;
    result.valid=input_y>=0 && input_y<int(input_width) &&
                 source_x>=0 && source_x<int(input_width);
    const unsigned safe_x=result.valid?unsigned(source_x):0u;
    result.address=(channel<<bank_shift)+(safe_x>>4);
    return result;
}

static inline unsigned dw7_normal_source_bank(unsigned lane,int dx) {
    return (int(lane)+dx)&15;
}

static inline unsigned dw7_p3_source_bank(unsigned lane,int dx) {
    return (2*int(lane)+dx)&15;
}

static inline bool pw2_signed40_fits(std::int64_t value) {
    return value>=-(std::int64_t(1)<<39) &&
           value<=((std::int64_t(1)<<39)-1);
}

static inline std::uint64_t pw2_signed40_bits(std::int64_t value) {
    return std::uint64_t(value)&((std::uint64_t(1)<<40)-1);
}

static inline std::int64_t pw2_signed40_sign_extend(std::uint64_t bits) {
    bits&=((std::uint64_t(1)<<40)-1);
    if(bits&(std::uint64_t(1)<<39)) bits|=~((std::uint64_t(1)<<40)-1);
    return static_cast<std::int64_t>(bits);
}

}  // namespace cnn_v10_candidate
