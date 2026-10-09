#include "candidate_adapter_contract.hpp"
#include "cnn_v10_storage_helpers.hpp"
#include "cnn_v10_pw2_storage.hpp"

namespace dual_lane_storage_dw7_opt_test {

Pw1Location candidate_pw1_map(std::uint32_t logical_bank,
                              std::uint32_t old_address,
                              std::uint32_t bank_depth) {
    const cnn_v10_candidate::Pw1PhysicalLocation location=
        cnn_v10_candidate::pw1_physical_location(
            logical_bank,old_address,2u*bank_depth);
    return Pw1Location{location.accepted,
                       static_cast<std::uint8_t>(location.physical_bank),
                       static_cast<std::uint8_t>(location.port),
                       location.physical_address};
}

Dw7Read candidate_dw7_fixed_bank_read(std::uint32_t input_width,
                                      std::uint32_t channel,
                                      std::uint32_t bank_shift,
                                      std::int32_t input_y,
                                      std::int32_t base_x,
                                      std::int32_t dx,
                                      std::uint32_t physical_bank) {
    const cnn_v10_candidate::Dw7FixedRead read=
        cnn_v10_candidate::dw7_fixed_bank_read(
            input_width,channel,bank_shift,input_y,base_x,dx,physical_bank);
    return Dw7Read{read.valid,static_cast<std::uint8_t>(read.physical_bank),
                   read.address};
}

void candidate_dw7_normal_reorder(
        const std::array<std::uint64_t,16>& bank_values,
        std::int32_t dx,
        std::array<std::uint64_t,16>& multiplier_inputs) {
    for(unsigned lane=0;lane<16;++lane) {
        const unsigned bank=
            cnn_v10_candidate::dw7_normal_source_bank(lane,dx);
        multiplier_inputs[lane]=bank_values[bank];
    }
}

void candidate_dw7_p3_reorder(
        const std::array<std::uint64_t,16>& bank_values,
        std::int32_t dx,
        std::array<std::uint64_t,16>& multiplier_inputs) {
    for(unsigned lane=0;lane<8;++lane) {
        const unsigned bank=cnn_v10_candidate::dw7_p3_source_bank(lane,dx);
        const std::uint64_t value=bank_values[bank];
        multiplier_inputs[lane]=value;
        multiplier_inputs[lane+8]=value;
    }
}

bool candidate_pack_signed40x4(const std::array<std::int64_t,4>& values,
                               std::array<std::uint32_t,5>& packed_words) {
    for(const std::int64_t value:values)
        if(!cnn_v10_candidate::pw2_signed40_fits(value)) return false;
    ap_int<48> lanes[4];
    for(unsigned lane=0;lane<4;++lane) lanes[lane]=values[lane];
    const cnn_v10_candidate::Pw2StoredColumn packed=
        cnn_v10_candidate::pw2_pack_column(lanes);
    std::array<std::uint32_t,5> next{};
    for(unsigned word=0;word<5;++word)
        next[word]=static_cast<std::uint32_t>(packed.range(word*32+31,word*32));
    packed_words=next;
    return true;
}

std::array<std::int64_t,4>
candidate_unpack_signed40x4(const std::array<std::uint32_t,5>& packed_words) {
    cnn_v10_candidate::Pw2StoredColumn packed=0;
    for(unsigned word=0;word<5;++word)
        packed.range(word*32+31,word*32)=packed_words[word];
    std::array<std::int64_t,4> values{};
    for(unsigned lane=0;lane<4;++lane)
        values[lane]=static_cast<long long>(
            cnn_v10_candidate::pw2_expand_lane(packed,lane));
    return values;
}

}  // namespace dual_lane_storage_dw7_opt_test
