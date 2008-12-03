#
# $Id$
#
%define url $URL$

%define name pyplnet
%define version 4.2
%define taglevel 0

%define release %{taglevel}%{?pldistro:.%{pldistro}}%{?date:.%{date}}

%{!?python_sitearch: %define python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib(1)")}

Summary: PlanetLab Network Configuration library
Name: %{name}
Version: %{version}
Release: %{release}
License: PlanetLab
Group: System Environment/Daemons
Source0: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

Vendor: PlanetLab
Packager: PlanetLab Central <support@planet-lab.org>
Distribution: PlanetLab %{plrelease}
URL: %(echo %{url} | cut -d ' ' -f 2)

Requires: python >= 2.4
BuildRequires: python, python-devel

%description
pyplnet is used to write the network configuration files based on the
configuration data recorded at PLC.

%prep
%setup -q

%build
python setup.py build

%install
rm -rf $RPM_BUILD_ROOT
python setup.py install --skip-build --root "$RPM_BUILD_ROOT"

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%{python_sitearch}/*

%changelog
* Tue Dec  2 2008 Daniel Hokka Zakrisson <daniel@hozac.com> - pyplnet-4.2-1
- initial release
