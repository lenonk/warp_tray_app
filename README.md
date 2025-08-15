# warp_tray_app
System tray app for starting and stopping Cloudflare WARP service

# Install
Just put the script where you want it and modify the .desktop file so that the "Exec=" line points to it, and put the .desktop file in ~/.config/autostart.

If you want to avoid it asking for a password every time, put 50.warp-svc.rules in /etc/polkit-1/rules.d/ and add your user to the wheel group.
