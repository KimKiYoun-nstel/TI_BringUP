BRINGUP_ROOT ?= $(abspath ../../..)

ifndef CC
$(error CC is not set)
endif

SRC := src/main.c
BUILD_DIR ?= $(BRINGUP_ROOT)/out/sk-am64b-r5f-early-boot/a53
BIN := $(BUILD_DIR)/sk_am64b_r5f_early_boot_check

CFLAGS += -O2 -g -Wall -Wextra -std=c11

.PHONY: all clean

all: $(BIN)

$(BUILD_DIR):
	mkdir -p "$@"

$(BIN): $(SRC) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -o "$@" $(SRC)

clean:
	rm -rf "$(BUILD_DIR)"
