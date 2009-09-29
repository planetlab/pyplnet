#
# $Id$
#
%define url $URL$

%define name pyplnet
%define version 4.3
%define taglevel 4

%define release %{taglevel}%{?pldistro:.%{pldistro}}%{?date:.%{date}}

%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

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
BuildArch: noarch

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
chmod +x $RPM_BUILD_ROOT/%{python_sitelib}/plnet.py
mkdir -p $RPM_BUILD_ROOT/%{_bindir}
ln -s %{python_sitelib}/plnet.py $RPM_BUILD_ROOT/%{_bindir}/plnet

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%{_bindir}/plnet
%{python_sitelib}/*

%changelog
* Tue Sep 29 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - pyplnet-4.3-4
- alias without a mac address: fix runtime error while issuing warning

* Tue Jun 09 2009 Stephen Soltesz <soltesz@cs.princeton.edu> - pyplnet-4.3-3
- this patch addresses mlab and other multi-interface node confgurations where
- the generated boot image and network config files are mis-named.

* Wed Apr 22 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - pyplnet-4.3-2
- handle wireless settings back again

* Fri Apr 17 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - pyplnet-4.3-1
- fixes for 4.3

* Tue Dec  2 2008 Daniel Hokka Zakrisson <daniel@hozac.com> - pyplnet-4.3-1
- initial release
