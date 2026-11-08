# GLeaks: build and install
#
# `make install` performs a per-user install that uses the system PyGObject, so
# it works without touching pip's externally-managed environment. Use
# PREFIX=/usr with sudo for a system-wide install.

APP_ID      := io.github.openapi.GLeaks
PYTHON      ?= python3
PREFIX      ?= $(HOME)/.local
DESTDIR     ?=
BINDIR      := $(PREFIX)/bin
LIBDIR      := $(PREFIX)/share/gleaks
DATADIR     := $(PREFIX)/share
APPSDIR     := $(DATADIR)/applications
ICONDIR     := $(DATADIR)/icons/hicolor
METAINFODIR := $(DATADIR)/metainfo
MIMEDIR     := $(DATADIR)/mime/packages

INSTALL     := install

.PHONY: all help check test start run demo-svg check-sites install uninstall deb flatpak clean

all: help

help:
	@echo "GLeaks targets:"
	@echo "  make start      Start the app locally from the source tree"
	@echo "  make test       Run the test suite"
	@echo "  make demo-svg   Regenerate the animated preview in docs/"
	@echo "  make check-sites  Check the profile index against the live sites"
	@echo "  make check      Byte-compile the sources and validate the desktop metadata"
	@echo "  make install    Install into $(PREFIX)"
	@echo "  make uninstall  Remove an install from $(PREFIX)"
	@echo "  make deb        Build a .deb into dist/"
	@echo "  make flatpak    Build and install the Flatpak (needs flatpak-builder)"
	@echo "  make clean      Remove build artifacts"

check:
	$(PYTHON) -m compileall -q gleaks
	appstreamcli validate --no-net data/$(APP_ID).metainfo.xml
	desktop-file-validate data/$(APP_ID).desktop

test:
	$(PYTHON) -m pytest -q

# data/ on XDG_DATA_DIRS lets GTK find the app icon without installing it.
start:
	XDG_DATA_DIRS="$(CURDIR)/data:$${XDG_DATA_DIRS:-/usr/local/share:/usr/share}" $(PYTHON) -m gleaks

run: start

check-sites:
	$(PYTHON) build-aux/dev/check_sites.py

demo-svg:
	$(PYTHON) build-aux/dev/make_demo_svg.py docs/gleaks-demo.svg

install:
	$(INSTALL) -d $(DESTDIR)$(LIBDIR)
	cp -r gleaks $(DESTDIR)$(LIBDIR)/
	find $(DESTDIR)$(LIBDIR) -name '__pycache__' -type d -prune -exec rm -rf {} +
	$(INSTALL) -d $(DESTDIR)$(BINDIR)
	printf '#!/bin/sh\nexport PYTHONPATH="%s:$$PYTHONPATH"\nexec %s -m gleaks "$$@"\n' \
		"$(LIBDIR)" "$(PYTHON)" > $(DESTDIR)$(BINDIR)/gleaks
	chmod +x $(DESTDIR)$(BINDIR)/gleaks
	$(INSTALL) -Dm644 data/$(APP_ID).desktop $(DESTDIR)$(APPSDIR)/$(APP_ID).desktop
	$(INSTALL) -Dm644 data/$(APP_ID).metainfo.xml $(DESTDIR)$(METAINFODIR)/$(APP_ID).metainfo.xml
	$(INSTALL) -Dm644 data/$(APP_ID).mime.xml $(DESTDIR)$(MIMEDIR)/$(APP_ID).xml
	$(INSTALL) -Dm644 data/icons/hicolor/scalable/apps/$(APP_ID).svg \
		$(DESTDIR)$(ICONDIR)/scalable/apps/$(APP_ID).svg
	$(INSTALL) -Dm644 data/icons/hicolor/symbolic/apps/$(APP_ID)-symbolic.svg \
		$(DESTDIR)$(ICONDIR)/symbolic/apps/$(APP_ID)-symbolic.svg
	@# Packages leave these caches to their own triggers.
	@if [ -z "$(DESTDIR)" ]; then $(MAKE) --no-print-directory refresh-caches; fi

uninstall:
	rm -f  $(DESTDIR)$(BINDIR)/gleaks
	rm -rf $(DESTDIR)$(LIBDIR)
	rm -f  $(DESTDIR)$(APPSDIR)/$(APP_ID).desktop
	rm -f  $(DESTDIR)$(METAINFODIR)/$(APP_ID).metainfo.xml
	rm -f  $(DESTDIR)$(MIMEDIR)/$(APP_ID).xml
	rm -f  $(DESTDIR)$(ICONDIR)/scalable/apps/$(APP_ID).svg
	rm -f  $(DESTDIR)$(ICONDIR)/symbolic/apps/$(APP_ID)-symbolic.svg
	@if [ -z "$(DESTDIR)" ]; then $(MAKE) --no-print-directory refresh-caches; fi

.PHONY: refresh-caches
refresh-caches:
	-update-desktop-database $(APPSDIR) 2>/dev/null
	-update-mime-database $(DATADIR)/mime 2>/dev/null
	-gtk-update-icon-cache -f -t $(ICONDIR) 2>/dev/null

deb:
	build-aux/deb/build-deb.sh dist

flatpak:
	flatpak-builder --user --install --force-clean build-aux/flatpak-build \
		build-aux/flatpak/$(APP_ID).yaml

clean:
	rm -rf build dist *.egg-info build-aux/flatpak-build .flatpak-builder .pytest_cache
	find gleaks tests -name '__pycache__' -type d -prune -exec rm -rf {} +
