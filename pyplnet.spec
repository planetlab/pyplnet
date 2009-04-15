#
# $Id$
#
%define url $URL$

%define name pyplnet
%define version 4.2
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
* Wed Apr 15 2009 Marc Fiuczynski <mef@cs.princeton.edu> - pyplnet-4.2-4
- - reimplementation of the ModProbe class to be more robust in parsing
- modprobe/blacklist files.
- - blacklist get/set methods
- - supports "include" modprobe command

* Tue Feb 24 2009 Marc Fiuczynski <mef@cs.princeton.edu> - pyplnet-4.2-3
- BUGFIX: the "program" argument needs to go with the the m.output() method.
- The bug is that the m.input() method does not take two args and python
- will raise an exception to indicate this.  However, the m.input()
- method was wrapped in a
- try:
- m.input(a,b)
- except:
- pass
- which masked this error.  The mainly visible side effect is that the
- specific modprobe.conf file is not parsed and so any previously
- written aliases and options are lost.

* Mon Dec 15 2008 Daniel Hokka Zakrisson <daniel@hozac.com> - pyplnet-4.2-2
- Work on PLCs running in Linux-VServer guests or other environments where /sys
- isn't mounted.

* Sat Dec 13 2008 Daniel Hokka Zakrisson <daniel@hozac.com> - pyplnet-4.2-1
- Rewrite sioc in Python.
- Add a plnet symlink to make it easier to run the script via plcsh.
- Set DNS servers/gateway for static configurations.
- Work with an empty tree.
- Use tempfile for temporary files.

* Tue Dec  2 2008 Daniel Hokka Zakrisson <daniel@hozac.com> - pyplnet-4.2-1
- initial release
