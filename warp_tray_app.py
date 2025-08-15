#!/usr/bin/env python3

import sys
import subprocess
import asyncio
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QPalette
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusReply

class ServiceMonitor(QObject):
    """Async service monitor using D-Bus for better integration"""
    statusChanged = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.systemd_interface = None
        self.setup_dbus()
        
    def setup_dbus(self):
        """Setup D-Bus connection to systemd"""
        bus = QDBusConnection.systemBus()
        if bus.isConnected():
            self.systemd_interface = QDBusInterface(
                "org.freedesktop.systemd1",
                "/org/freedesktop/systemd1",
                "org.freedesktop.systemd1.Manager",
                bus
            )
    
    def get_service_status(self):
        """Get service status via D-Bus"""
        if not self.systemd_interface:
            return self._fallback_status_check()
        
        try:
            # Get unit object path
            reply = self.systemd_interface.call("GetUnit", "warp-svc.service")
            if reply.type() == QDBusReply.ReplyType.Error:
                return False
            
            unit_path = reply.value()
            unit_interface = QDBusInterface(
                "org.freedesktop.systemd1",
                unit_path,
                "org.freedesktop.systemd1.Unit",
                QDBusConnection.systemBus()
            )
            
            active_state = unit_interface.property("ActiveState")
            return active_state == "active"
        except Exception:
            return self._fallback_status_check()
    
    def _fallback_status_check(self):
        """Fallback to systemctl if D-Bus fails"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "warp-svc"], 
                capture_output=True, 
                text=True, 
                timeout=3
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False

class WarpTrayApp(QObject):
    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        
        # Qt6 has automatic high DPI scaling enabled by default
        # No need to set AA_UseHighDpiPixmaps anymore
        
        # Check if system tray is available
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("System tray is not available")
            sys.exit(1)
        
        # Initialize service monitor
        self.service_monitor = ServiceMonitor()
        self.service_monitor.statusChanged.connect(self.on_status_changed)
        
        # Create system tray icon with adaptive theming
        self.tray_icon = QSystemTrayIcon()
        self.current_status = False
        
        # Create context menu
        self.setup_menu()
        
        # Create adaptive icons
        self.create_adaptive_icons()
        
        # Set initial icon before showing
        self.update_icon()
        
        # Update status and setup monitoring
        self.update_status()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(3000)  # Check every 3 seconds
        
        # Show the tray icon
        self.tray_icon.show()
        
        # Handle tray icon activation
        self.tray_icon.activated.connect(self.tray_activated)
        
        # Listen for theme changes (KDE6 adaptive theming)
        self.app.paletteChanged.connect(self.on_palette_changed)
    
    def setup_menu(self):
        """Setup context menu with modern Qt6 actions"""
        self.menu = QMenu("Warp Service")
        
        # Status display
        self.status_action = QAction("Checking...")
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        
        self.menu.addSeparator()
        
        # Quick toggle (main action)
        #self.toggle_action = QAction("Connect")
        #self.toggle_action.triggered.connect(self.toggle_service)
        #self.menu.addAction(self.toggle_action)
        
        #self.menu.addSeparator()
        
        # Force start/stop actions
        self.start_action = QAction("▶ Connect Service")
        self.start_action.triggered.connect(lambda: self.set_service_state(True))
        self.menu.addAction(self.start_action)
        
        self.stop_action = QAction("⏸ Disconnect Service")
        self.stop_action.triggered.connect(lambda: self.set_service_state(False))
        self.menu.addAction(self.stop_action)
        
        # Restart action
        self.restart_action = QAction("↻ Restart Service")
        self.restart_action.triggered.connect(self.restart_service)
        self.menu.addAction(self.restart_action)
        
        self.menu.addSeparator()
        
        # Exit action
        self.exit_action = QAction("✕ Exit")
        self.exit_action.triggered.connect(self.app.quit)
        self.menu.addAction(self.exit_action)
        
        self.tray_icon.setContextMenu(self.menu)
    
    def create_adaptive_icons(self):
        """Create adaptive cloud icons that follow KDE theme"""
        self.icons = {}
        palette = self.app.palette()
        
        # Get theme colors
        text_color = palette.color(QPalette.ColorRole.WindowText)
        highlight_color = palette.color(QPalette.ColorRole.Highlight)
        success_color = QColor(46, 160, 67)  # Modern green
        inactive_color = text_color.lighter(130)
        
        # Create cloud icons for different states
        for state, color in [("active", success_color), ("inactive", inactive_color)]:
            pixmap = QPixmap(64, 64)
            pixmap.fill(QColor(0, 0, 0, 0))
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw cloud shape
            self.draw_cloud(painter, color, state == "active")
            
            painter.end()
            self.icons[state] = QIcon(pixmap)
    
    def draw_cloud(self, painter, color, is_active):
        """Draw a modern cloud shape"""
        painter.setBrush(color)
        painter.setPen(QColor(0, 0, 0, 0))  # No outline
        
        # Cloud base - main body
        painter.drawEllipse(20, 35, 30, 18)
        
        # Cloud puffs - left side
        painter.drawEllipse(12, 28, 20, 20)
        painter.drawEllipse(15, 32, 16, 16)
        
        # Cloud puffs - right side  
        painter.drawEllipse(35, 25, 22, 22)
        painter.drawEllipse(40, 30, 18, 18)
        
        # Cloud puffs - top
        painter.drawEllipse(25, 20, 18, 18)
        painter.drawEllipse(30, 18, 16, 16)
        
        # Add subtle glow effect for active state
        if is_active:
            glow_color = color.lighter(150)
            glow_color.setAlpha(60)
            painter.setBrush(glow_color)
            
            # Outer glow
            painter.drawEllipse(18, 33, 34, 22)
            painter.drawEllipse(10, 26, 24, 24)
            painter.drawEllipse(33, 23, 26, 26)
            painter.drawEllipse(23, 18, 22, 22)
    
    def on_palette_changed(self):
        """Handle KDE theme changes"""
        self.create_adaptive_icons()
        self.update_icon()
    
    def update_icon(self):
        """Update tray icon based on current state"""
        icon_state = "active" if self.current_status else "inactive"
        self.tray_icon.setIcon(self.icons[icon_state])

    def update_status(self):
        """Update service status"""
        is_active = self.service_monitor.get_service_status()
        
        if is_active != self.current_status:
            self.current_status = is_active
            self.on_status_changed(is_active)
    
    def on_status_changed(self, is_active):
        """Handle status change"""
        self.current_status = is_active

        if is_active:
            self.status_action.setText("● Warp Service: Active")
            self.status_action.setEnabled(False)
            #self.toggle_action.setText("Disconnect")
            self.tray_icon.setToolTip("Warp Service is: Active\nClick to disconnect")
            self.start_action.setEnabled(False)
            self.stop_action.setEnabled(True)
        else:
            self.status_action.setText("○ Warp Service: Inactive")
            self.status_action.setEnabled(False)
            #self.toggle_action.setText("Connect")
            self.tray_icon.setToolTip("Warp Service is: Inactive\nClick to connect")
            self.start_action.setEnabled(True)
            self.stop_action.setEnabled(False)
        
        self.update_icon()
    
    async def toggle_service_async(self):
        """Async service toggle for better responsiveness"""
        await asyncio.to_thread(self.toggle_service)
    
    def toggle_service(self):
        """Toggle the service state"""
        self.set_service_state(not self.current_status)
    
    def set_service_state(self, start=True):
        """Start or stop the service with better error handling"""
        action = "start" if start else "stop"
        action_name = "Starting" if start else "Stopping"
        
        try:
            # Show immediate feedback
            self.tray_icon.showMessage(
                "Warp Service", 
                f"{action_name} service...", 
                QSystemTrayIcon.MessageIcon.Information, 
                1000
            )
            
            # Use systemctl with better error handling
            result = subprocess.run(
                ["systemctl", action, "warp-svc"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                success_msg = "Service started" if start else "Service stopped"
                self.tray_icon.showMessage(
                    "Warp Service", 
                    success_msg, 
                    QSystemTrayIcon.MessageIcon.Information, 
                    2000
                )
            else:
                error_msg = result.stderr or f"Failed to {action} service"
                self.tray_icon.showMessage(
                    "Warp Service Error", 
                    error_msg, 
                    QSystemTrayIcon.MessageIcon.Critical, 
                    4000
                )
            
            # Force immediate status update
            self.update_status()
            
        except subprocess.TimeoutExpired:
            self.tray_icon.showMessage(
                "Warp Service", 
                f"Timeout while {action_name.lower()} service", 
                QSystemTrayIcon.MessageIcon.Warning, 
                3000
            )
        except Exception as e:
            self.tray_icon.showMessage(
                "Warp Service Error", 
                f"Error: {str(e)}", 
                QSystemTrayIcon.MessageIcon.Critical, 
                4000
            )
    
    def restart_service(self):
        """Restart the service"""
        try:
            self.tray_icon.showMessage(
                "Warp Service", 
                "Restarting service...", 
                QSystemTrayIcon.MessageIcon.Information, 
                1000
            )
            
            result = subprocess.run(
                ["systemctl", "restart", "warp-svc"], 
                capture_output=True, 
                text=True, 
                timeout=15
            )
            
            if result.returncode == 0:
                self.tray_icon.showMessage(
                    "Warp Service", 
                    "Service restarted", 
                    QSystemTrayIcon.MessageIcon.Information, 
                    2000
                )
            else:
                self.tray_icon.showMessage(
                    "Warp Service Error", 
                    result.stderr or "Failed to restart service", 
                    QSystemTrayIcon.MessageIcon.Critical, 
                    4000
                )
            
            self.update_status()
            
        except Exception as e:
            self.tray_icon.showMessage(
                "Warp Service Error", 
                f"Restart failed: {str(e)}", 
                QSystemTrayIcon.MessageIcon.Critical, 
                4000
            )
    
    def tray_activated(self, reason):
        """Handle tray icon clicks with modern interaction"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left click
            self.toggle_service()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:  # Middle click
            self.restart_service()
    
    def run(self):
        """Run the application with proper Qt6 event loop"""
        # Set application metadata for better Wayland integration
        self.app.setApplicationName("Warp Service Toggle")
        self.app.setApplicationDisplayName("Warp Tray")
        self.app.setApplicationVersion("2.0")
        self.app.setOrganizationName("WarpTray")
        
        return self.app.exec()

if __name__ == "__main__":
    app = WarpTrayApp()
    sys.exit(app.run())
