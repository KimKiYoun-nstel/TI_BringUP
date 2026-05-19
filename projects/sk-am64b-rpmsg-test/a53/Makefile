BRINGUP_ROOT ?= $(abspath ../../..)

ifndef CC
$(error CC is not set)
endif

ifdef SDKTARGETSYSROOT
SYSROOT_INCLUDE := $(SDKTARGETSYSROOT)/usr/include
SYSROOT_LIB := $(SDKTARGETSYSROOT)/usr/lib
else ifdef LINUX_DEVKIT
SYSROOT_INCLUDE := $(LINUX_DEVKIT)/sysroots/aarch64-oe-linux/usr/include
SYSROOT_LIB := $(LINUX_DEVKIT)/sysroots/aarch64-oe-linux/usr/lib
else
$(error Neither SDKTARGETSYSROOT nor LINUX_DEVKIT is set)
endif

SRC := src/main.c
BUILD_DIR ?= $(BRINGUP_ROOT)/out/sk-am64b-rpmsg-test/a53
BIN := $(BUILD_DIR)/sk_am64b_rpmsg_test_a53

CFLAGS += -O2 -g -Wall -Wextra -I$(SYSROOT_INCLUDE)
LDFLAGS += -L$(SYSROOT_LIB)
LDLIBS += -lti_rpmsg_char

.PHONY: all clean

all: $(BIN)

$(BUILD_DIR):
	mkdir -p "$@"

$(BIN): $(SRC) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -o "$@" $(SRC) $(LDFLAGS) $(LDLIBS)

clean:
	rm -rf "$(BUILD_DIR)"
