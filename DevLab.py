#!/usr/bin/env python3
"""Create and destroy the disposable proot containers builds run in."""

import os
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path

HOME = Path.home()
DEVLAB_DIR = HOME / ".devlab"
KNOWN = ("DEBIAN-13", "UBUNTU-24", "FEDORA-44")
TIMEZONE = "Asia/Jerusalem"

CYAN = "\033[1;36m"
RESET = "\033[0m"

def log(msg):
	print(f"{CYAN}{msg}{RESET}", flush=True)

DEBIAN_SOURCES = """\
Types: deb deb-src
URIs: http://deb.debian.org/debian
Suites: trixie trixie-updates
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp

Types: deb deb-src
URIs: http://deb.debian.org/debian-security
Suites: trixie-security
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp
"""

UBUNTU_SOURCES = """\
Types: deb deb-src
URIs: http://ports.ubuntu.com/ubuntu-ports/
Suites: noble noble-updates noble-backports
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb deb-src
URIs: http://ports.ubuntu.com/ubuntu-ports/
Suites: noble-security
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
"""

FEDORA_REPO = """\
[fedora]
name=Fedora $releasever - $basearch
metalink=https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=$basearch
enabled=1
metadata_expire=7d
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$releasever-$basearch
skip_if_unavailable=False

[fedora-source]
name=Fedora $releasever - Source
metalink=https://mirrors.fedoraproject.org/metalink?repo=fedora-source-$releasever&arch=$basearch
enabled=1
metadata_expire=7d
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$releasever-$basearch
skip_if_unavailable=False
"""

FEDORA_UPDATES_REPO = """\
[updates]
name=Fedora $releasever - $basearch - Updates
metalink=https://mirrors.fedoraproject.org/metalink?repo=updates-released-f$releasever&arch=$basearch
enabled=1
countme=1
repo_gpgcheck=0
type=rpm
gpgcheck=1
metadata_expire=6h
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$releasever-$basearch
skip_if_unavailable=False

[updates-source]
name=Fedora $releasever - Updates Source
metalink=https://mirrors.fedoraproject.org/metalink?repo=updates-released-source-f$releasever&arch=$basearch
enabled=1
repo_gpgcheck=0
type=rpm
gpgcheck=1
metadata_expire=6h
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$releasever-$basearch
skip_if_unavailable=False
"""

PIP_CONF = "[global]\nextra-index-url = https://reubeninstitute.duckdns.org/pip/simple/\n"

REUBEN_DEB_PUBLIC_KEY = """-----BEGIN PGP PUBLIC KEY BLOCK-----

mQINBGq1VEwBEACtrBrMvEDsTMEu6t+Z+mEgJU7h+qUdC7nPNHjp35QiVNOWWlIl
Mjk+ZsRLdMOo94CKPN3V41sOrha5cEgDNeZ/9WJa2D9Vp6Lv94Xu8IIJSwDQDEv6
tf2lnzbAEO4x4WUTB7pSj4Z3gAE1sfBVhNAMHE3UwJWjV9Baima98vjATQj8lk4N
rAjL5OHuply2VAiJD1nkUX/kZ/NKad+k3EgkCH2axEKzQ6LGNfVuWfoaVKV4JGf6
inWdsGtVxUmVWVNVOFMLowU6pF8yQvPGuWqvUKer9tGxrku3TU3vEPp+nP29Xtpm
gDvbHkKcYzhtemW+oE5HaHAR59ytw3qME/3Cl2dupfF8YErOwEa6aLQgm71LnT5k
uuqZ7qDAdUQFbSdaKz2GQFQ0KAO2CSOukIFSuOPBXeGTOEbJv2gE+sZf/BNruD2d
5/C5yrQqLUJEnQEzI+k6Nj3lMbs+746CBtR6ZByxozoQFiY+HplJSUTIJzRN/Vrc
97jKjUXlBQigSTEofwQgO84iTAbcMTB9Xj9GU5AC15nS1742mM3qEEzJV/FsK/iG
oaZuAn33/ZLk/1zPEgSBXE6DSDCMOuVBLretUssf6FOWJN5+kHI0j9uni3naXLaH
rrJUo5apgE9bnKYqta4Ys1VfzoZp1DPmZlKWWPlBhqtjtkWcm0/kmIxO0QARAQAB
tDJSZXViZW4gSW5zdGl0dXRlIDxyb2JlcnQud2FsbG5lci5lZHdhcmRAZ21haWwu
Y29tPokCUQQTAQoAOxYhBGVnFxZtebLjwnw+/4B8zCDybP8IBQJqtVRMAhsDBQsJ
CAcCAiICBhUKCQgLAgQWAgMBAh4HAheAAAoJEIB8zCDybP8I7sMP/jF3pRmKYYRB
1M+DOZBMW6YCeuScDnjHXFljqWUdigIw+pSNkXkHNzeElRx5QLOHa/6AvZZ3AUBx
yyMUrtNcOsYdfoX36zHO9qHNa+lcAASrA8Zdp5V60yELCoLzyBxN8x3XkuQZyXc8
Hrw3hxx1+T8VF5JTYFSHMIQdK+37YeQljhupsi+6M3ImIAFbYLb7faYHWlSJQ1BV
0n5IIxzRj1oQl2yRzOZo4B4oE+b8HHxQ62hd5n7SZoMNLIlfpUMWAWW/tSDTNqvj
UseAyfCCC5YVjH6ZSUhLhBlO3IqmgzwGT3zjnVNvEh6/5oOhWBA6oWfDiWbWYDI8
gLideGk6V2LU56bATogODE0NWz71CAtBYLpkfgve1AIdwT0u2kpJu2UBSkkl67AT
kdcOFPJHIesMYA6S5l3onLpGyZvjWcLS+xwYBK8z01H5oUmZbvjSVwGeMKkyvGx7
ZHL6RZwJkdMQW223Xtv28WahZwQbBhYmYNv25R74vH2gFzJGbSk7r/kpf1UKzY3K
iuFWeWCuJnFHfcqWjm+K6LBiuXWg5iCeg1g3+gfKCGjvmudOMYgNozJUMx9GvQBH
r0JBS9/veX9lE+Zta9zuhCyNeJxAdUMbQJMBeQUNStzkMAOS+U3vGQq4eF0uDezp
ZwUBy0eGmwZKBNYDPiBuq7Vkv4+siUT5
=y5OE
-----END PGP PUBLIC KEY BLOCK-----"""

IMAGES = {
	"DEBIAN-13": "debian:trixie",
	"UBUNTU-24": "ubuntu:24.04",
	"FEDORA-44": "fedora:44",
}


def _require_known(name):
	if name not in KNOWN:
		raise ValueError(f"unknown container {name!r}; known: {', '.join(KNOWN)}")


def bootstrap(name):
	"""(Re)build <name>.tar.xz from scratch: fresh proot-distro install
	of the upstream image, updated, upgraded, with mc and the timezone
	set. Nothing Reuben-specific goes in here -- that's provision()'s
	job, applied at create_container time rather than baked into the
	snapshot.

	Packing goes through `proot-distro backup`, not a plain tar: proot-distro
	leaves behind a .l2s/ folder of placeholder symlinks standing in for
	hardlinks the storage can't actually make, and only proot-distro's own
	backup code knows how to resolve those back into real hardlinks. A
	generic `proot --link2symlink tar` over the install directly hits an
	ELOOP on that folder instead. So: back up with proot-distro (correct
	hardlinks, but archive entries are named "<name>/rootfs/..." plus a
	"<name>/manifest.json"), then rewrite the archive entry-by-entry,
	stream to stream -- never touching a real filesystem again, which
	would just reintroduce the same can't-make-hardlinks problem -- to
	strip that "<name>/rootfs/" prefix and drop manifest.json, producing
	a plain archive with etc/, usr/, bin, ... at the top: the same shape
	as today's file, which create_container's extraction expects.
	"""
	_require_known(name)
	log(f"Bootstrapping {name}...")
	subprocess.run(["proot-distro", "remove", name], check=False)
	log("Installing image...")
	subprocess.run(
		["proot-distro", "install", IMAGES[name], "--name", name], check=True,
	)
	tz_symlink = f"ln -sf /usr/share/zoneinfo/{TIMEZONE} /etc/localtime"
	if name == "FEDORA-44":
		cmd = f"dnf -y upgrade && dnf -y install mc && {tz_symlink}"
	else:
		cmd = (
			"DEBIAN_FRONTEND=noninteractive apt-get update && apt-get -y full-upgrade"
			f" && DEBIAN_FRONTEND=noninteractive apt-get -y install mc tzdata && {tz_symlink}"
		)
	log("Updating and configuring system...")
	subprocess.run(
		["proot-distro", "login", name, "--", "sh", "-c", cmd], check=True,
	)

	DEVLAB_DIR.mkdir(exist_ok=True)
	log("Creating backup...")
	backup_path = DEVLAB_DIR / f".{name}.bootstrap-backup.tar.xz"
	subprocess.run(
		["proot-distro", "backup", name, "--output", str(backup_path)],
		check=True,
	)
	subprocess.run(["proot-distro", "remove", name], check=True)

	log("Repackaging archive...")
	prefix = f"{name}/rootfs/"
	final_path = DEVLAB_DIR / f"{name}.tar.xz"
	try:
		with tarfile.open(backup_path, "r|xz") as src, \
				tarfile.open(final_path, "w|xz") as dst:
			count = 0
			for member in src:
				if not member.name.startswith(prefix):
					continue  # the manifest.json entry, or the rootfs dir itself
				member.name = member.name[len(prefix):]
				if not member.name:
					continue
				if member.islnk() and member.linkname.startswith(prefix):
					member.linkname = member.linkname[len(prefix):]
				fileobj = src.extractfile(member) if member.isreg() else None
				dst.addfile(member, fileobj)
				count += 1
				if count % 1000 == 0:
					print(f"  {count} files processed...", flush=True)
	finally:
		backup_path.unlink(missing_ok=True)
	log(f"Bootstrap complete: {final_path}")


PROVISION_MODES = ("bare", "dev")

DEV_PACKAGES = (
	"gnupg apt-utils dpkg-dev git lintian devscripts debhelper fakeroot quilt"
)


def provision(name, mode="bare"):
	"""Add Reuben Institute's own stuff on top of an already-bare
	container: ca-certificates/curl (so https repos can be reached at
	all), the Reuben apt repo (debian/ubuntu only), and the Reuben pip
	repo. Everything else -- OS-baseline update/upgrade, mc, timezone --
	is bootstrap()'s job, already baked into <name>.tar.xz.

	mode="dev" additionally installs the deb packaging toolchain used
	for the apt repo work (gpg, dpkg-dev, apt-ftparchive, git, lintian,
	devscripts, debhelper, fakeroot, quilt) -- debian/ubuntu only, since
	that toolchain has no Fedora equivalent here.

	The OS is identified from the extracted tree's own /etc/os-release,
	not trusted from the folder name, and anything not exactly one of
	the three recognized OS/major-version combos is refused rather than
	guessed at. Only the major version is checked (e.g. ubuntu-24 vs
	ubuntu-22), since that's what determines repo suite names.
	"""
	if mode not in PROVISION_MODES:
		raise ValueError(f"unknown mode {mode!r}; known: {', '.join(PROVISION_MODES)}")
	log(f"Provisioning {name} (mode: {mode})...")
	root = HOME / name

	os_id = ""
	version_id = ""
	os_release = root / "etc/os-release"
	if os_release.exists():
		for line in os_release.read_text().splitlines():
			if line.startswith("ID="):
				os_id = line.split("=", 1)[1].strip('"')
			elif line.startswith("VERSION_ID="):
				version_id = line.split("=", 1)[1].strip('"')

	# os-release's ID is authoritative and checked first: Ubuntu also
	# ships /etc/debian_version for backward-compat (a useless
	# "trixie/sid"-style placeholder), so probing for that file's mere
	# existence would misidentify ubuntu as debian.
	debian_version = root / "etc/debian_version"
	if os_id == "debian" and debian_version.exists():
		major = debian_version.read_text().strip().split(".")[0]
	elif os_id:
		major = version_id.split(".")[0]
	else:
		major = ""

	if os_id == "debian" and major == "13":
		os_key = "debian13"
	elif os_id == "ubuntu" and major == "24":
		os_key = "ubuntu24"
	elif os_id == "fedora" and major == "44":
		os_key = "fedora44"
	else:
		raise ValueError(
			f"unrecognized or unsupported OS/version (id={os_id!r}, "
			f"major={major!r}) in {name}, refusing to provision"
		)

	# Reuben Institute's own flat apt-ftparchive repo (debian/ubuntu only
	# -- no rpm/dnf equivalent exists yet). The signing key is embedded
	# in this script for offline deployments.
	reuben_apt = (
		"mkdir -p /etc/apt/sources.list.d"
		" && echo 'deb [signed-by=/etc/apt/keyrings/reuben-deb.asc]"
		" https://reubeninstitute.duckdns.org/deb/ ./'"
		" > /etc/apt/sources.list.d/reuben.list"
	)

	# pip config is OS-agnostic (same file regardless of apt vs dnf), so
	# it's written once here rather than duplicated per OS above.
	(root / "etc").mkdir(parents=True, exist_ok=True)
	(root / "etc/pip.conf").write_text(PIP_CONF)

	if os_key == "fedora44":
		cmd = "dnf -y install ca-certificates curl"
	else:
		# Write the embedded signing key directly to the container
		keyrings_dir = root / "etc/apt/keyrings"
		keyrings_dir.mkdir(parents=True, exist_ok=True)
		(keyrings_dir / "reuben-deb.asc").write_text(REUBEN_DEB_PUBLIC_KEY)

		cmd = (
			"DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install curl ca-certificates"
			f" && {reuben_apt}"
		)
		if mode == "dev":
			cmd += f" && DEBIAN_FRONTEND=noninteractive apt-get -y install {DEV_PACKAGES}"

	log("Installing dependencies...")
	login_container(name, cmd)
	log(f"Provisioning complete")


def login_container(name, command=None):
	"""Drop into a container via proot, or run a single command inside it.

	Replaces the old start.sh: with no command, this execs proot directly
	(replacing the current process, same as start.sh's `exec`) for an
	interactive --login shell. With a command, it runs that one command
	via `bash --login -c` and returns/raises on its exit status, same as
	proot-distro's own `login <name> -- <command>` convention.
	"""
	_require_known(name)
	target = HOME / name
	if not target.is_dir():
		raise FileNotFoundError(f"container {name!r} does not exist at {target}")

	env = os.environ.copy()
	env.pop("LD_PRELOAD", None)

	argv = ["proot", "--kill-on-exit", "--link2symlink", "-0", "-r", str(target)]
	argv += ["-b", "/dev", "-b", "/proc", "-b", "/sys"]
	argv += ["-b", f"{target}/root:/dev/shm"]
	argv += ["-b", "/proc/self/fd/2:/dev/stderr"]
	argv += ["-b", "/proc/self/fd/1:/dev/stdout"]
	argv += ["-b", "/proc/self/fd/0:/dev/stdin"]
	argv += ["-b", "/dev/urandom:/dev/random"]
	argv += ["-b", "/proc/self/fd:/dev/fd"]
	for fake in ("stat", "vmstat", "version"):
		fake_path = target / "proc/fakethings" / fake
		if fake_path.is_file():
			argv += ["-b", f"{fake_path}:/proc/{fake}"]
	argv += ["-b", "/data/data/com.termux/files/usr/tmp:/tmp"]
	argv += ["-b", "/data/data/com.termux/files/usr/tmp/.X11-unix:/tmp/.X11-unix"]
	argv += ["-b", "/sdcard"]
	argv += ["-w", "/root"]
	argv += [
		"/usr/bin/env", "-i",
		"MOZ_FAKE_NO_SANDBOX=1",
		"HOME=/root",
		"PATH=/usr/local/sbin:/usr/local/bin:/bin:/usr/bin:/sbin:/usr/sbin:/usr/games:/usr/local/games",
		f"TERM={env.get('TERM', '')}",
		"LANG=C.UTF-8",
		"/bin/bash", "--login",
	]

	if command:
		subprocess.run(argv + ["-c", command], env=env, check=True)
	else:
		os.execvpe("proot", argv, env)


def destroy_container(name):
	_require_known(name)
	target = HOME / name
	if not target.exists():
		return
	log(f"Removing {name}...")
	for root, dirs, files in os.walk(target):
		for d in dirs:
			p = os.path.join(root, d)
			try:
				os.chmod(p, os.stat(p).st_mode | stat.S_IWUSR | stat.S_IXUSR)
			except OSError:
				pass
		for f in files:
			p = os.path.join(root, f)
			if not os.path.islink(p):
				try:
					os.chmod(p, os.stat(p).st_mode | stat.S_IWUSR)
				except OSError:
					pass
	shutil.rmtree(target)
	log(f"Removed {name}")


def create_container(name, mode="bare"):
	_require_known(name)
	destroy_container(name)
	log(f"Creating {name}...")
	target = HOME / name
	target.mkdir(parents=True)
	log("Extracting container image...")
	subprocess.run(
		["proot", "--link2symlink", "tar", "--numeric-owner", "--delay-directory-restore",
		 "-xpJf", str(DEVLAB_DIR / f"{name}.tar.xz"), "-C", str(target)],
		check=True,
	)
	if name == "FEDORA-44":
		cmd = "dnf -y upgrade"
	else:
		cmd = "DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade"
	log("Updating container packages...")
	login_container(name, cmd)
	provision(name, mode=mode)
	log(f"Container {name} ready")


if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser(description="Create and destroy disposable proot containers")
	subparsers = parser.add_subparsers(dest="command", required=True)

	name_choices = list(KNOWN) + ["all"]

	bootstrap_parser = subparsers.add_parser("bootstrap", help="Rebuild container image from scratch")
	bootstrap_parser.add_argument("name", choices=name_choices, help="Container name or 'all'")

	create_parser = subparsers.add_parser("create", help="Create a new container")
	create_parser.add_argument("name", choices=name_choices, help="Container name or 'all'")
	create_parser.add_argument("--mode", choices=PROVISION_MODES, default="bare", help="Provisioning mode (default: bare)")

	destroy_parser = subparsers.add_parser("destroy", help="Remove a container")
	destroy_parser.add_argument("name", choices=name_choices, help="Container name or 'all'")

	provision_parser = subparsers.add_parser("provision", help="Provision an existing container")
	provision_parser.add_argument("name", choices=name_choices, help="Container name or 'all'")
	provision_parser.add_argument("--mode", choices=PROVISION_MODES, default="bare", help="Provisioning mode (default: bare)")

	login_parser = subparsers.add_parser("login", help="Log into a container, or run one command inside it")
	login_parser.add_argument("name", choices=KNOWN, help="Container name")
	login_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run (default: interactive shell)")

	args = parser.parse_args()

	names = KNOWN if args.name == "all" else (args.name,)

	if args.command == "bootstrap":
		for name in names:
			bootstrap(name)
	elif args.command == "create":
		for name in names:
			create_container(name, mode=args.mode)
	elif args.command == "destroy":
		for name in names:
			destroy_container(name)
	elif args.command == "provision":
		for name in names:
			provision(name, mode=args.mode)
	elif args.command == "login":
		cmd_words = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
		login_container(args.name, " ".join(cmd_words) if cmd_words else None)
