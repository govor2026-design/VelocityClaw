import unittest
from velocity_claw.config.settings import load_settings
from velocity_claw.memory.store import MemoryStore


class MemoryStoreTest(unittest.TestCase):
    def test_memory_store_initializes(self):
        settings = load_settings()
        settings.memory_enabled = False
        store = MemoryStore(settings)
        self.assertFalse(store.enabled)


if __name__ == "__main__":
    unittest.main()
