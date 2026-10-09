#include "candidate_adapter_contract.hpp"

#include <array>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace test = dual_lane_storage_dw7_opt_test;

static std::vector<std::int64_t> fields(const std::string& line) {
    std::vector<std::int64_t> out;
    std::stringstream stream(line);
    std::string token;
    while (std::getline(stream, token, '\t')) out.push_back(std::stoll(token));
    return out;
}

static std::vector<std::vector<std::int64_t>> table(const std::string& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open oracle table: " + path);
    std::vector<std::vector<std::int64_t>> rows;
    std::string line;
    std::getline(input, line);  // Header.
    while (std::getline(input, line)) if (!line.empty()) rows.push_back(fields(line));
    return rows;
}

[[noreturn]] static void fail(const std::string& message) {
    throw std::runtime_error(message);
}

static void test_pw1(const std::string& root, std::uint64_t& checks) {
    for (const auto& row : table(root + "/pw1_bank_map.tsv")) {
        if (row.size() != 7) fail("bad PW1 oracle width");
        const auto got = test::candidate_pw1_map(
            static_cast<std::uint32_t>(row[0]), static_cast<std::uint32_t>(row[1]),
            static_cast<std::uint32_t>(row[2]));
        if (got.accepted != static_cast<bool>(row[3]) ||
            (got.accepted &&
             (static_cast<std::int64_t>(got.physical_bank) != row[4] ||
              static_cast<std::int64_t>(got.port) != row[5] ||
              static_cast<std::int64_t>(got.physical_address) != row[6]))) {
            fail("PW1 logical-to-physical mapping mismatch");
        }
        if (got.accepted && (got.physical_bank >= 8 || got.port >= 2 ||
                             got.physical_address >= 4u * static_cast<std::uint32_t>(row[2]))) {
            fail("PW1 mapping escaped the 8-bank true-dual-port address space");
        }
        ++checks;
    }
    constexpr std::array<std::uint32_t, 2> bank_depths{1u, 64u};
    for (const std::uint32_t bank_depth : bank_depths) {
        for (std::uint32_t old_address = 0; old_address < 2u * bank_depth; ++old_address) {
            std::array<std::array<bool, 2>, 8> occupied{};
            for (std::uint32_t logical_bank = 0; logical_bank < 16; ++logical_bank) {
                const auto got = test::candidate_pw1_map(logical_bank, old_address, bank_depth);
                if (!got.accepted || got.physical_bank >= 8 || got.port >= 2)
                    fail("PW1 simultaneous 16-lane mapping rejected or escaped");
                if (occupied[got.physical_bank][got.port])
                    fail("PW1 simultaneous 16-lane mapping aliases a bank port");
                occupied[got.physical_bank][got.port] = true;
                ++checks;
            }
            for (const auto& bank : occupied)
                if (!bank[0] || !bank[1]) fail("PW1 did not occupy both ports of every physical bank");
        }
    }
}

static std::uint64_t encoded_value(const test::Dw7Read& read) {
    return (static_cast<std::uint64_t>(read.address) << 8) | read.physical_bank;
}

static void test_dw7_normal(const std::string& root, std::uint64_t& checks,
                            std::uint64_t& value_signature) {
    const auto rows = table(root + "/dw7_normal.tsv");
    for (std::size_t begin = 0; begin < rows.size();) {
        const std::int64_t case_id = rows[begin][0];
        std::size_t end = begin;
        while (end < rows.size() && rows[end][0] == case_id) ++end;
        if (end - begin != 16) fail("normal DW7 oracle case does not contain 16 fixed banks");
        const auto& head = rows[begin];
        std::array<std::uint64_t, 16> bank_values{};
        std::array<bool, 16> bank_seen{};
        for (std::size_t bank = 0; bank < 16; ++bank) {
            const auto& expected = rows[begin + bank];
            const auto actual = test::candidate_dw7_fixed_bank_read(
                static_cast<std::uint32_t>(head[1]), static_cast<std::uint32_t>(head[2]),
                static_cast<std::uint32_t>(head[3]), static_cast<std::int32_t>(head[4]),
                static_cast<std::int32_t>(head[5]), static_cast<std::int32_t>(head[6]),
                static_cast<std::uint32_t>(bank));
            if (actual.valid != static_cast<bool>(expected[8]) ||
                static_cast<std::int64_t>(actual.physical_bank) != expected[7] ||
                static_cast<std::int64_t>(actual.address) != expected[9]) {
                fail("normal DW7 fixed-bank read mismatch");
            }
            if (actual.physical_bank >= 16) fail("normal DW7 bank outside 16-bank contract");
            if (bank_seen[actual.physical_bank]) fail("normal DW7 duplicate fixed-bank read");
            bank_seen[actual.physical_bank] = true;
            const std::uint32_t first = static_cast<std::uint32_t>(head[2]) << static_cast<std::uint32_t>(head[3]);
            const std::uint32_t chunks = 1u << static_cast<std::uint32_t>(head[3]);
            if (actual.address < first || actual.address >= first + chunks)
                fail("normal DW7 safe address outside current channel row");
            bank_values[actual.physical_bank] = actual.valid ? encoded_value(actual) : 0;
            ++checks;
        }
        std::array<std::uint64_t, 16> multiplier_inputs{};
        test::candidate_dw7_normal_reorder(
            bank_values, static_cast<std::int32_t>(head[6]), multiplier_inputs);
        for (std::size_t lane = 0; lane < 16; ++lane) {
            const auto expected_bank = static_cast<std::size_t>(rows[begin + lane][10]);
            if (expected_bank >= 16 || multiplier_inputs[lane] != bank_values[expected_bank])
                fail("normal DW7 source-value reorder mismatch");
            value_signature ^= multiplier_inputs[lane] + 0x9E3779B97F4A7C15ull * lane;
            ++checks;
        }
        begin = end;
    }
}

static void test_dw7_p3(const std::string& root, std::uint64_t& checks,
                        std::uint64_t& value_signature) {
    const auto rows = table(root + "/dw7_p3.tsv");
    for (std::size_t begin = 0; begin < rows.size();) {
        const std::int64_t case_id = rows[begin][0];
        std::size_t end = begin;
        while (end < rows.size() && rows[end][0] == case_id) ++end;
        if (end - begin != 16) fail("P3 DW7 oracle case does not contain 16 fixed banks");
        const auto& head = rows[begin];
        std::array<std::uint64_t, 16> bank_values{};
        std::array<bool, 16> bank_seen{};
        for (std::size_t bank = 0; bank < 16; ++bank) {
            const auto& expected = rows[begin + bank];
            const auto actual = test::candidate_dw7_fixed_bank_read(
                static_cast<std::uint32_t>(head[1]), static_cast<std::uint32_t>(head[2]),
                static_cast<std::uint32_t>(head[3]), static_cast<std::int32_t>(head[4]),
                static_cast<std::int32_t>(head[5]), static_cast<std::int32_t>(head[6]),
                static_cast<std::uint32_t>(bank));
            if (actual.valid != static_cast<bool>(expected[8]) ||
                static_cast<std::int64_t>(actual.physical_bank) != expected[7] ||
                static_cast<std::int64_t>(actual.address) != expected[9])
                fail("P3 DW7 fixed-bank read mismatch");
            if (actual.physical_bank >= 16) fail("P3 DW7 bank outside 16-bank contract");
            if (bank_seen[actual.physical_bank]) fail("P3 DW7 duplicate fixed-bank read");
            bank_seen[actual.physical_bank] = true;
            const std::uint32_t first = static_cast<std::uint32_t>(head[2]) << static_cast<std::uint32_t>(head[3]);
            const std::uint32_t chunks = 1u << static_cast<std::uint32_t>(head[3]);
            if (actual.address < first || actual.address >= first + chunks)
                fail("P3 DW7 safe address outside current channel row");
            bank_values[actual.physical_bank] = actual.valid ? encoded_value(actual) : 0;
            ++checks;
        }
        std::array<std::uint64_t, 16> multiplier_inputs{};
        test::candidate_dw7_p3_reorder(
            bank_values, static_cast<std::int32_t>(head[6]), multiplier_inputs);
        for (std::size_t lane = 0; lane < 8; ++lane) {
            const auto& expected = rows[begin + lane];
            const auto selected_bank = static_cast<std::size_t>(expected[11]);
            if (expected[10] != static_cast<std::int64_t>(lane) ||
                selected_bank >= 16 ||
                expected[12] != static_cast<std::int64_t>(lane) ||
                expected[13] != static_cast<std::int64_t>(lane + 8))
                fail("P3 DW7 source selection or multiplier duplication mismatch");
            const std::uint64_t expected_value = bank_values[selected_bank];
            if (multiplier_inputs[lane] != expected_value ||
                multiplier_inputs[lane + 8] != expected_value)
                fail("P3 DW7 duplicated multiplier values differ from selected bank");
            value_signature ^= (multiplier_inputs[lane] + lane) ^
                               (multiplier_inputs[lane + 8] + lane + 8u);
            ++checks;
        }
        begin = end;
    }
}

static void test_signed40(const std::string& root, std::uint64_t& checks) {
    constexpr std::array<std::uint32_t, 5> sentinel{
        0xA5A5A5A5u, 0x5A5A5A5Au, 0xC3C3C3C3u, 0x3C3C3C3Cu, 0x96966969u};
    for (const auto& row : table(root + "/signed40_packed4.tsv")) {
        if (row.size() != 15) fail("bad signed40 oracle width");
        std::array<std::int64_t, 4> input{row[1], row[2], row[3], row[4]};
        auto packed = sentinel;
        const bool accepted = test::candidate_pack_signed40x4(input, packed);
        if (accepted != static_cast<bool>(row[5])) fail("signed40 overflow acceptance mismatch");
        if (!accepted) {
            if (packed != sentinel) fail("signed40 overflow rejection was not atomic");
        } else {
            for (std::size_t word = 0; word < 5; ++word)
                if (packed[word] != static_cast<std::uint32_t>(row[6 + word])) fail("signed40 packed bits mismatch");
            const auto unpacked = test::candidate_unpack_signed40x4(packed);
            for (std::size_t lane = 0; lane < 4; ++lane)
                if (unpacked[lane] != row[11 + lane]) fail("signed40 unpack/sign-extension mismatch");
        }
        ++checks;
    }
}

int main(int argc, char** argv) {
    try {
        if (argc != 2) fail("usage: tb_dual_lane_storage_dw7_opt ORACLE_DIR");
        std::uint64_t pw1_checks = 0, normal_checks = 0, p3_checks = 0, packed_checks = 0;
        std::uint64_t signature = 0;
        test_pw1(argv[1], pw1_checks);
        test_dw7_normal(argv[1], normal_checks, signature);
        test_dw7_p3(argv[1], p3_checks, signature);
        test_signed40(argv[1], packed_checks);
        std::cout << "DUAL_LANE_STORAGE_DW7_OPT_NATIVE_PASS"
                  << " pw1=" << pw1_checks
                  << " dw7_normal=" << normal_checks
                  << " dw7_p3=" << p3_checks
                  << " signed40=" << packed_checks
                  << " signature=" << signature << "\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << "DUAL_LANE_STORAGE_DW7_OPT_NATIVE_FAIL " << error.what() << "\n";
        return EXIT_FAILURE;
    }
}
