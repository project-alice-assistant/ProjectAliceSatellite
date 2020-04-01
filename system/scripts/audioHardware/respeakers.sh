#!/usr/bin/env bash

cd /home/$(logname) || exit

if [[ -d "/home/$(logname)/seeed-voicecard" ]]; then
  rm -rf /home/$(logname)/seeed-voicecard
fi

git clone https://github.com/respeaker/seeed-voicecard.git /home/$(logname)/seeed-voicecard

sed -i -e 's/  install_kernel/#  install_kernel/' /home/$(logname)/seeed-voicecard/install.sh
sed -i -e 's/  check_kernel_headers/#  check_kernel_headers/' /home/$(logname)/seeed-voicecard/install.sh


chmod +x /home/$(logname)/seeed-voicecard/install.sh
./home/$(logname)/seeed-voicecard/install.sh

sleep 1

systemctl enable seeed-voicecard
