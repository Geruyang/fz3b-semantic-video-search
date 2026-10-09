#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L

/* Fixed-address, read-only clock register audit for the FZ3B experiment.
 * Addresses are the Zynq UltraScale+ MPSoC CRF_APB/CRL_APB register
 * addresses from UG1087.  The program accepts no arguments and never maps
 * writable memory.
 */
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <unistd.h>

struct fixed_register {
	uint64_t address;
	const char *name;
};

static const struct fixed_register registers[] = {
	{UINT64_C(0xFD1A0020), "CRF_APB.APLL_CTRL"},
{UINT64_C(0xFD1A0024), "CRF_APB.APLL_CFG"},
{UINT64_C(0xFD1A0028), "CRF_APB.APLL_FRAC_CFG"},
	{UINT64_C(0xFD1A002C), "CRF_APB.DPLL_CTRL"},
	{UINT64_C(0xFD1A0038), "CRF_APB.VPLL_CTRL"},
{UINT64_C(0xFD1A003C), "CRF_APB.VPLL_CFG"},
{UINT64_C(0xFD1A0040), "CRF_APB.VPLL_FRAC_CFG"},
	{UINT64_C(0xFD1A0044), "CRF_APB.PLL_STATUS"},
	{UINT64_C(0xFD1A0060), "CRF_APB.ACPU_CTRL"},
	{UINT64_C(0xFD1A0080), "CRF_APB.DDR_CTRL"},
	{UINT64_C(0xFF5E0020), "CRL_APB.IOPLL_CTRL"},
	{UINT64_C(0xFF5E0030), "CRL_APB.RPLL_CTRL"},
	{UINT64_C(0xFF5E00C0), "CRL_APB.PL0_REF_CTRL"},
{UINT64_C(0xFF5E00C4), "CRL_APB.PL1_REF_CTRL"},
{UINT64_C(0xFF5E00C8), "CRL_APB.PL2_REF_CTRL"},
{UINT64_C(0xFF5E00CC), "CRL_APB.PL3_REF_CTRL"},
};

int main(int argc, char **argv)
{
	long page_size;
	int fd;
	int result = 0;
	size_t i;

	(void)argv;
	if (argc != 1) {
		fprintf(stderr, "no arguments accepted; fixed read-only register set\n");
		return 2;
	}

	page_size = sysconf(_SC_PAGESIZE);
	if (page_size < 4 ||
	    ((uint64_t)page_size & ((uint64_t)page_size - 1)) != 0) {
		fprintf(stderr, "invalid page size\n");
		return 2;
	}

	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) {
		fprintf(stderr, "open /dev/mem: %s\n", strerror(errno));
		return 2;
	}

	for (i = 0; i < sizeof(registers) / sizeof(registers[0]); ++i) {
		uint64_t address = registers[i].address;
		uint64_t page = address & ~((uint64_t)page_size - 1);
		size_t offset = (size_t)(address - page);
		void *mapping = mmap(NULL, (size_t)page_size, PROT_READ,
			MAP_SHARED, fd, (off_t)page);
		const volatile uint32_t *reg;
		uint32_t value;

		if (mapping == MAP_FAILED) {
			fprintf(stderr, "mmap 0x%08" PRIX64 ": %s\n",
				address, strerror(errno));
			result = 2;
			break;
		}

		reg = (const volatile uint32_t *)
			((const unsigned char *)mapping + offset);
		value = *reg;
		if (printf("0x%08" PRIX64 " 0x%08" PRIX32 " %s\n",
			   address, value, registers[i].name) < 0 ||
		    fflush(stdout) != 0) {
			result = 2;
		}
		if (munmap(mapping, (size_t)page_size) != 0)
			result = 2;
		if (result)
			break;
	}

	if (close(fd) != 0)
		result = 2;
	return result;
}
