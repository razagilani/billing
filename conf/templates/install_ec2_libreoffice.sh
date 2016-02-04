#!/usr/bin/env bash

# =============================================================================
# This script downloads and install LibreOffice.  This script should be used on
# Amazon's verison of EC2 Linux.
# =============================================================================

set -e 

LIBREOFFICE_VERSION="4.4.7"
LIBREOFFICE_NAME="LibreOffice_${LIBREOFFICE_VERSION}_Linux_x86-64_rpm"
LIBREOFFICE_ARCHIVE="${LIBREOFFICE_NAME}.tar.gz"
LIBREOFFICE_URL="http://download.documentfoundation.org/libreoffice/stable/${LIBREOFFICE_VERSION}/rpm/x86_64/${LIBREOFFICE_ARCHIVE}"
FORCE_DOWNLOAD="0"
DRYRUN="0"
CLEANUP="1"
EXTRA="http://mirror.centos.org/centos/6/os/x86_64/Packages/dbus-glib-0.86-6.el6.x86_64.rpm"

function download {
	WORKDIR=`mktemp -d` || exit 1
	cd /tmp
	if [ -e "$LIBREOFFICE_ARCHIVE" ] && [ "$FORCE_DOWNLOAD" -eq "1" ]; then
		rm "$LIBREOFFICE_ARCHIVE"
		wget "$LIBREOFFICE_URL"
	elif [ -e "$LIBREOFFICE_ARCHIVE" ]; then
		echo "LibreOffice archive already exists"
	else
		echo "Downloading ${LIBREOFFICE_ARCHIVE}"
		wget "$LIBREOFFICE_URL"
	fi
	tar -xvf "$LIBREOFFICE_ARCHIVE" -C "${WORKDIR}"
        cd ${WORKDIR}/*
	ls -l
}

function install {
	cd RPMS/
	# Remove libobasis4.3-gnome-integration rpm file. Amazon EC2 Linux is 
	# command-line only.
	rpm -Uvh "$EXTRA"
	for f in *gnome*; do mv "$f" "${f/.rpm/.noinstall}"; done
	yum -y install *rpm
}

function cleanup {
	echo "Removing temporary directory ${WORKDIR}"
	rm -rvf "${WORKDIR}"
}

function usage {
        echo "Usage: ./install_ec2_libreoffice.sh [OPTIONS]"
        echo "  -f Force script to redownload and reinstall Libreoffice."
	echo "  -d Perform dry-run to download but not install LibreOffice."
        echo "  -n Have script preserve temporary files."
	echo "  -h Print help dialog (this message) and exit."
}

function main {
	#Download and extract the binarnies
	download
	if [ "$DRYRUN" -eq "0" ]; then
                #Install the RPM archives using yum.
		install
        fi
	if [ "$CLEANUP" -eq "1" ]; then
		#Remove the temporary directories.
		cleanup
	else
		echo "Temporary files are located in ${WORKDIR}"
	fi
}

trap "cleanup" SIGINT SIGTERM

#Verify user is root.
if [ "$(id -u)" != "0" ]; then
	echo "This script must be run as root" 1>&2
	usage
	exit 1
fi

while getopts "fdnh" opt; do
        case ${opt} in
		f)
			FORCE_DOWNLOAD="1"
			echo "Forcing download of LibreOffice"
			;;
                d)
                        DRYRUN="1"
                        echo "Dry run enabled."
                        ;;
		n)	
			CLEANUP="0"
			echo "No cleanup of temporary files"
			;;
                h)
			usage
			exit 0
			;;
		*)
                        usage
                        exit 0
                        ;;
        esac
done

main
