#!/bin/sh
# Run on TMDS64EVM as root. This intentionally persists the Qbu test baseline.
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

disable_network_file 05-eth1-tsn-control.network
disable_network_file 06-eth2-tsn-endpoint.network

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

cat > "$network_dir/12-eth2-l2only.network" <<'EOF'
[Match]
Name=eth2
KernelCommandLine=!root=/dev/nfs

[Link]
RequiredForOnline=no

[Network]
LinkLocalAddressing=no
DHCP=no
IPv6AcceptRA=no
EOF

systemctl disable --now ti-tsn-dscp-pcp-tmds.service 2>/dev/null || true
systemctl daemon-reload

printf '%s\n' 'TMDS Qbu clean baseline installed. Reboot or restart systemd-networkd before testing.'
