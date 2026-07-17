import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useLinksStore } from '../linksStore';
import * as api from '../../utils/api';

// Mock the apiFetch function
vi.mock('../../utils/api', () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    statusText: string;
    data: any;
    constructor(status: number, statusText: string, data: any) {
      super(statusText);
      this.status = status;
      this.statusText = statusText;
      this.data = data;
    }
  }
}));

describe('Links Zustand Store — Optimistic Sync & Rollback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset store state manually
    useLinksStore.setState({
      links: [],
      syncStatus: 'idle',
      entities: [
        { id: 'entity-b-id', label: 'Beta Node', owner_role: 'user', created_at: new Date().toISOString() }
      ],
      error: null
    });
  });

  it('performs optimistic insert and confirms on successful server response', async () => {
    const fakeServerResponse = {
      id: 'real-link-id',
      entity_a_id: 'real-entity-a-id',
      entity_b_id: 'entity-b-id',
      private_notes: 'Highly confidential notes',
      created_at: new Date().toISOString(),
      created: true,
      entity_a: { id: 'real-entity-a-id', label: 'Alpha Node', owner_role: 'user', created_at: new Date().toISOString() },
      entity_b: { id: 'entity-b-id', label: 'Beta Node', owner_role: 'user', created_at: new Date().toISOString() }
    };

    // Set up mock apiFetch resolver
    const apiFetchMock = vi.mocked(api.apiFetch).mockResolvedValueOnce(fakeServerResponse);

    const store = useLinksStore.getState();
    
    // Call syncLink, but don't await yet to inspect intermediate state
    const syncPromise = store.syncLink('mock-token-payload', 'entity-b-id', 'Highly confidential notes');

    // Intermediate state check: optimistic item should be prepended
    const intermediateState = useLinksStore.getState();
    expect(intermediateState.syncStatus).toBe('optimistic');
    expect(intermediateState.links).toHaveLength(1);
    expect(intermediateState.links[0].id).toContain('temp-');
    expect(intermediateState.links[0].entity_a?.label).toBe('Resolving opaque entity...');
    expect(intermediateState.links[0].private_notes).toBe('Highly confidential notes');

    // Await API completion
    await syncPromise;

    // Confirmed state check: temp item replaced with real backend values
    const finalState = useLinksStore.getState();
    expect(finalState.syncStatus).toBe('confirmed');
    expect(finalState.links).toHaveLength(1);
    expect(finalState.links[0].id).toBe('real-link-id');
    expect(finalState.links[0].entity_a?.label).toBe('Alpha Node');
    expect(apiFetchMock).toHaveBeenCalledTimes(1);
  });

  it('performs optimistic insert and rolls back the list on server rejection', async () => {
    const errorResponse = {
      name: 'ApiError',
      status: 409,
      statusText: 'Conflict',
      data: { detail: 'Token has already been used (replay rejected)' }
    };

    // Set up mock apiFetch rejector
    const apiFetchMock = vi.mocked(api.apiFetch).mockRejectedValueOnce(errorResponse);

    const store = useLinksStore.getState();
    
    // Trigger syncLink
    const syncPromise = store.syncLink('reused-token-payload', 'entity-b-id', 'Notes to rollback');

    // Ensure optimistic item is in place
    expect(useLinksStore.getState().links).toHaveLength(1);
    expect(useLinksStore.getState().syncStatus).toBe('optimistic');

    // Wait for resolution (expecting it to fail)
    await expect(syncPromise).rejects.toBeDefined();

    // Final state check: optimistic link rolled back, status set to error
    const finalState = useLinksStore.getState();
    expect(finalState.syncStatus).toBe('error');
    expect(finalState.links).toHaveLength(0); // completely removed
    expect(finalState.error).toContain('Token has already been used');
    expect(apiFetchMock).toHaveBeenCalledTimes(1);
  });
});
