"""
Telemetry: subscription methods (sampling lives in telemetry.py).
"""



class TelemetryInterface:
    """Subscribe / Unsubscribe for io.github.archer.Control1.Telemetry."""

    def _m_Telemetry_Subscribe(self, sender, interval_ms):
        self.telemetry.subscribe(sender, interval_ms)

    def _m_Telemetry_Unsubscribe(self, sender):
        self.telemetry.unsubscribe(sender)

