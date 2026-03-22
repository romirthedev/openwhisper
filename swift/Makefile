PRODUCT_NAME = OpenWhisper
BUILD_DIR    = .build/release
APP_DIR      = $(PRODUCT_NAME).app
CONTENTS     = $(APP_DIR)/Contents
MACOS_DIR    = $(CONTENTS)/MacOS
RESOURCES_DIR = $(CONTENTS)/Resources

# Project root (one level up from swift/)
PROJECT_ROOT := $(shell cd .. && pwd)

.PHONY: all build bundle clean run

all: bundle

build:
	swift build -c release

bundle: build
	@echo "==> Assembling $(APP_DIR)..."
	@rm -rf $(APP_DIR)
	@mkdir -p $(MACOS_DIR) $(RESOURCES_DIR)
	@cp $(BUILD_DIR)/$(PRODUCT_NAME) $(MACOS_DIR)/$(PRODUCT_NAME)

	@# Write Info.plist
	@/usr/libexec/PlistBuddy -c "Add :CFBundleName string $(PRODUCT_NAME)" \
		-c "Add :CFBundleIdentifier string com.openwhisper.app" \
		-c "Add :CFBundleVersion string 1.0" \
		-c "Add :CFBundleShortVersionString string 1.0" \
		-c "Add :CFBundleExecutable string $(PRODUCT_NAME)" \
		-c "Add :CFBundlePackageType string APPL" \
		-c "Add :LSMinimumSystemVersion string 13.0" \
		-c "Add :LSUIElement bool true" \
		-c "Add :NSMicrophoneUsageDescription string OpenWhisper needs microphone access to record your voice." \
		-c "Add :NSPrincipalClass string NSApplication" \
		$(CONTENTS)/Info.plist

	@# Copy Python resources
	@ln -sf $(PROJECT_ROOT)/src $(CONTENTS)/Resources/src || true
	@ln -sf $(PROJECT_ROOT)/.venv $(CONTENTS)/Resources/.venv 2>/dev/null || true

	@echo "==> Built: $(APP_DIR)"
	@echo "    Run with: open $(APP_DIR)"
	@echo "    Or: $(MACOS_DIR)/$(PRODUCT_NAME)"

run: bundle
	$(MACOS_DIR)/$(PRODUCT_NAME)

clean:
	rm -rf $(APP_DIR) .build
