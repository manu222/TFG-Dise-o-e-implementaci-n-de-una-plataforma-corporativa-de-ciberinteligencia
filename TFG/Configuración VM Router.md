
# To-Do List

- [ ] Creación VM machine en proxmox
- [ ] Config forward
- [ ] Config NAT
- [ ] Claves ssh
- [ ] NetConfig


## 1. Creación VM proxmox



## 2. Configuración Red


### /etc/nftables.conf 
```bash
flush ruleset

table ip nat {
  chain postrouting {
    type nat hook postrouting priority 100;
    oif "ens19" masquerade
  }
}

table ip filter {
  chain forward {
    type filter hook forward priority 0;
    ct state established,related accept
    iif "ens18" oif "ens19" accept
  }
}
```

### /etc/sysctl.conf  

```bash
# Uncomment the next line to enable packet forwarding for IPv4
net.ipv4.ip_forward=1
```

### ip addr

```bash
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host noprefixroute 
       valid_lft forever preferred_lft forever
2: ens18: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether bc:24:11:5a:e5:27 brd ff:ff:ff:ff:ff:ff
    altname enp0s18
    inet 10.0.0.1/24 brd 10.0.0.255 scope global ens18
       valid_lft forever preferred_lft forever
    inet6 fe80::be24:11ff:fe5a:e527/64 scope link 
       valid_lft forever preferred_lft forever
3: ens19: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether 02:00:00:6b:5a:13 brd ff:ff:ff:ff:ff:ff
    altname enp0s19
    inet 145.239.16.147/32 scope global ens19
       valid_lft forever preferred_lft forever
    inet6 fe80::ff:fe6b:5a13/64 scope link 
       valid_lft forever preferred_lft forever
```

### /etc/netplan/01-netcfg.yaml     

```yml
network:
  version: 2
  renderer: networkd
  ethernets:
    ens19:
      dhcp4: no
      dhcp6: no
      addresses: [145.239.16.147/32]
      gateway4: 145.239.16.254
      nameservers:
        addresses: [208.67.222.222,208.67.220.220,8.8.8.8]
      routes:
      - to: 145.239.16.254/32
        via: 0.0.0.0
        scope: link
    ens18:
      addresses: [10.0.0.1/24]

```
