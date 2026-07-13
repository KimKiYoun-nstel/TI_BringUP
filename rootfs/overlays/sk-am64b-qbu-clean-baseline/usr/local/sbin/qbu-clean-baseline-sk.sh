#!/bin/sh
# Run on SK-AM64B as root. This intentionally persists the Qbu test baseline.
set -eu

network_dir=/etc/systemd/network

disable_network_file()
{
	file="$network_dir/$1"
	disabled="$file.qbu-disabled"

	if [ -e "$file" ] && [ ! -e "$disabled" ]; then
		mv "$file" "$disabled"
	fi
}

disable_network_file 05-br-tsn.netdev
disable_network_file 06-eth0-br-tsn-slave.network
disable_network_file 07-eth1-br-tsn-slave.network
disable_network_file 08-br-tsn.network

cat > "$network_dir/09-eth0-l2only.network" <<'EOF'
[Match]
Name=eth0
KernelCommandLine=!root=/dev/nfs

[Link]
RequiredForOnline=no

[Network]
LinkLocalAddressing=no
DHCP=no
IPv6AcceptRA=no
EOF

cat > "$network_dir/11-eth1-l2only.network" <<'EOF'
[Match]
Name=eth1
KernelCommandLine=!root=/dev/nfs

[Link]
RequiredForOnline=no

[Network]
LinkLocalAddressing=no
DHCP=no
IPv6AcceptRA=no
EOF

systemctl disable --now ti-tsn-dscp-pcp-sk.service 2>/dev/null || true
systemctl daemon-reload

printf '%s\n' 'SK Qbu clean baseline installed. Reboot or restart systemd-networkd before testing.'
