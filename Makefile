PREFIX := /data/data/com.termux/files/usr
G := $(PREFIX)/glibc/lib
LOADER := $(G)/ld-linux-aarch64.so.1
DEST := $(PREFIX)/lib/claude-code-glibc
BIN := $(DEST)/claude
WRAPPER := $(PREFIX)/bin/claude
VERSION ?= latest
BUILD := build
PKGVER ?= 0.1.0

.PHONY: install-claude uninstall-claude deb clean

install-claude:
	@for c in npm tar python3; do \
		command -v "$$c" >/dev/null 2>&1 || { echo "Missing '$$c'. Run: pkg install nodejs python"; exit 1; }; \
	done
	@[ -e "$(LOADER)" ] || { echo "glibc loader not found. Run: pkg install glibc-repo glibc-runner"; exit 1; }
	@[ "$$(head -c 4 "$(LOADER)" | tail -c 3)" = "ELF" ] || { echo "$(LOADER) is not an ELF file. Reinstall it: pkg reinstall glibc"; exit 1; }
	@if [ -e "$(G)/ld-real.so" ]; then \
		rm -f "$(LOADER)"; mv "$(G)/ld-real.so" "$(LOADER)"; echo "Restored original glibc loader."; \
	fi
	rm -f "$(BIN).new"
	@version="$(VERSION)"; \
	if [ "$$version" = "latest" ]; then version="$$(npm view @anthropic-ai/claude-code version)"; fi; \
	echo "Installing Claude Code $$version ..."; \
	tmp="$$(mktemp -d)"; \
	trap "rm -rf '$$tmp'" EXIT; \
	( cd "$$tmp" && \
		npm pack "@anthropic-ai/claude-code-linux-arm64@$$version" --silent >/dev/null && \
		tar xzf ./*.tgz && \
		[ -f package/claude ] || { echo "Download failed: package/claude not found"; exit 1; } && \
		python3 - package/claude "$(LOADER)" <<'PY'
import struct, sys

path, loader = sys.argv[1], sys.argv[2]
new = loader.encode() + b"\0"

with open(path, "r+b") as f:
		eh = f.read(64)
		if eh[:4] != b"\x7fELF" or eh[4] != 2 or eh[5] != 1:
				sys.exit("not a 64-bit little-endian ELF")
		(phoff,) = struct.unpack_from("<Q", eh, 32)
		phentsize, phnum = struct.unpack_from("<HH", eh, 54)

		ents = []
		for i in range(phnum):
				f.seek(phoff + i * phentsize)
				t, _, off, _, _, fsz, _, _ = struct.unpack("<IIQQQQQQ", f.read(56))
				ents.append((t, off, fsz))

		interp = [i for i, e in enumerate(ents) if e[0] == 3]	# PT_INTERP
		if len(interp) != 1:
				sys.exit("no unique PT_INTERP")
		ii = interp[0]
		start, size = ents[ii][1], ents[ii][2]
		end = start + size

		# absorb PT_NOTE segments that directly follow the interpreter string
		notes = []
		while True:
				nxt = [i for i, e in enumerate(ents)
							 if e[0] == 4 and i not in notes and end <= e[1] < end + 8]
				if not nxt:
						break
				notes.append(nxt[0])
				end = ents[nxt[0]][1] + ents[nxt[0]][2]

		room = end - start
		if len(new) > room:
				sys.exit("not enough room for interpreter path: need %d bytes, have %d"
								 % (len(new), room))

		f.seek(start)
		f.write(new + b"\0" * (room - len(new)))
		f.seek(phoff + ii * phentsize + 32)					# p_filesz, p_memsz
		f.write(struct.pack("<QQ", len(new), len(new)))
		for i in notes:															# PT_NOTE -> PT_NULL
				f.seek(phoff + i * phentsize)
				f.write(struct.pack("<I", 0))

print("Patched interpreter: %d bytes at offset 0x%x (room %d)" % (len(new), start, room))
PY
	); \
	mkdir -p "$(DEST)"; \
	cp "$$tmp/package/claude" "$(BIN).new"; \
	chmod 755 "$(BIN).new"; \
	mv "$(BIN).new" "$(BIN)"
	@echo '#!$(PREFIX)/bin/sh' > "$(WRAPPER)"
	@echo 'unset LD_PRELOAD' >> "$(WRAPPER)"
	@echo 'exec "$(BIN)" "$$@"' >> "$(WRAPPER)"
	chmod 755 "$(WRAPPER)"
	@hash -r 2>/dev/null || true
	@echo "Verifying ..."
	"$(WRAPPER)" --version
	env -u LD_PRELOAD "$(BIN)" --version
	@echo "Done. Run: claude"

uninstall-claude:
	@if [ -f "$(WRAPPER)" ] && grep -q "claude-code-glibc" "$(WRAPPER)" 2>/dev/null; then \
		rm -f "$(WRAPPER)"; echo "Removed $(WRAPPER)"; \
	fi
	@if [ -e "$(G)/ld-real.so" ]; then \
		rm -f "$(LOADER)"; mv "$(G)/ld-real.so" "$(LOADER)"; echo "Restored $(LOADER)"; \
	fi
	rm -rf "$(DEST)"
	@hash -r 2>/dev/null || true
	@echo "Uninstalled."

deb:
	@[ -f "$(WRAPPER)" ] || { echo "Nothing installed yet. Run: make install-claude"; exit 1; }
	@[ -f "$(BIN)" ] || { echo "Nothing installed yet. Run: make install-claude"; exit 1; }
	rm -rf "$(BUILD)/pkg"
	install -Dm755 "$(WRAPPER)" "$(BUILD)/pkg$(PREFIX)/bin/claude"
	install -Dm755 "$(BIN)" "$(BUILD)/pkg$(PREFIX)/lib/claude-code-glibc/claude"
	mkdir -p "$(BUILD)/pkg/DEBIAN"
	sed "s/^Version:.*/Version: $(PKGVER)/" debian/control > "$(BUILD)/pkg/DEBIAN/control"
	dpkg-deb --build "$(BUILD)/pkg" "$(BUILD)/claude-termux_$(PKGVER)_aarch64.deb"

clean:
	rm -rf "$(BUILD)"
