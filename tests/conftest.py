"""Shared pytest configuration.

Runtime capability flags are intentionally not forced here. Individual tests
must opt into shell or git access explicitly so production-safe defaults remain
testable and test order cannot change security-policy results.
"""
