// Runs before every test file, ahead of its imports: Dexie reads the global indexedDB when it
// loads, so the in-memory fake has to be installed first.
import 'fake-indexeddb/auto'
