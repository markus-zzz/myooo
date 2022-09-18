#ifndef MYOOO_TEST_H
#define MYOOO_TEST_H

#ifndef TEST_FUNC_NAME
#  define TEST_FUNC_NAME mytest
#  define TEST_FUNC_TXT "mytest"
#  define TEST_FUNC_RET mytest_ret
#endif

#define RVTEST_RV32U
#define TESTNUM x28

#define RVTEST_CODE_BEGIN		\
	.text;				\
  nop

#define RVTEST_PASS			\
	lui	a0,0x80000000>>12;	\
	addi	a1,zero,'O';		\
	addi	a2,zero,'K';		\
	addi	a3,zero,'\n';		\
  sw a1, 0(a0); \
  sw a2, 0(a0); \
  sw a3, 0(a0); \
  ebreak; \
  j 0

#define RVTEST_FAIL			\
	lui	a0,0x80000000>>12;	\
	addi	a1,zero,'E';		\
	addi	a2,zero,'R';		\
	addi	a3,zero,'O';		\
	addi	a4,zero,'\n';		\
  sw a1, 0(a0); \
  sw a2, 0(a0); \
  sw a2, 0(a0); \
  sw a3, 0(a0); \
  sw a2, 0(a0); \
  sw a4, 0(a0); \
  ebreak; \
  j 0

#define RVTEST_CODE_END
#define RVTEST_DATA_BEGIN .balign 4;
#define RVTEST_DATA_END

#endif
