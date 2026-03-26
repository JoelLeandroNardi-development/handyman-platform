from app.breakers.breaker import CircuitBreaker

cb_auth = CircuitBreaker("auth-service", 5, 10)
cb_availability = CircuitBreaker("availability-service", 5, 10)
cb_booking = CircuitBreaker("booking-service", 5, 10)
cb_handyman = CircuitBreaker("handyman-service", 5, 10)
cb_match = CircuitBreaker("match-service", 5, 10)
cb_notification = CircuitBreaker("notification-service", 5, 10)
cb_user = CircuitBreaker("user-service", 5, 10)