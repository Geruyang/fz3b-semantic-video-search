#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace dual_lane_storage_dw7_opt_test {

struct Pw1Location {
    bool accepted;
    std::uint8_t physical_bank;
    std::uint8_t port;
    std::uint32_t physical_address;
};

struct Dw7Read {
    bool valid;
    std::uint8_t physical_bank;
    std::uint32_t address;
};

// The future candidate adapter must be a thin wrapper around the named
// candidate helpers.  It must not reproduce either mapping formula.
// candidate_pw1_map passes 2*bank_depth as the candidate helper's
// logical_bank_depth argument because old_address spans two image rows.
Pw1Location candidate_pw1_map(std::uint32_t logical_bank,
                              std::uint32_t old_address,
                              std::uint32_t bank_depth);

Dw7Read candidate_dw7_fixed_bank_read(std::uint32_t input_width,
                                      std::uint32_t channel,
                                      std::uint32_t bank_shift,
                                      std::int32_t input_y,
                                      std::int32_t base_x,
                                      std::int32_t dx,
                                      std::uint32_t physical_bank);

void candidate_dw7_normal_reorder(
    const std::array<std::uint64_t, 16>& bank_values,
    std::int32_t dx,
    std::array<std::uint64_t, 16>& multiplier_inputs);

void candidate_dw7_p3_reorder(
    const std::array<std::uint64_t, 16>& bank_values,
    std::int32_t dx,
    std::array<std::uint64_t, 16>& multiplier_inputs);

bool candidate_pack_signed40x4(const std::array<std::int64_t, 4>& values,
                               std::array<std::uint32_t, 5>& packed);

std::array<std::int64_t, 4>
candidate_unpack_signed40x4(const std::array<std::uint32_t, 5>& packed);

}  // namespace dual_lane_storage_dw7_opt_test
