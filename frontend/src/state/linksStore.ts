import { create } from 'zustand';
import { apiFetch, ApiError } from '../utils/api';

export type RequestStatus = 'idle' | 'pending' | 'optimistic' | 'confirmed' | 'error';
export type NetworkStatus = 'online' | 'offline' | 'reconnecting';

export interface Entity {
  id: string;
  label: string;
  owner_role: string;
  created_at: string;
}

export interface Link {
  id: string;
  entity_a_id: string;
  entity_b_id: string;
  private_notes: string | null;
  created_at: string;
  entity_a?: Entity;
  entity_b?: Entity;
}

export interface CursorPageResponse {
  items: Link[];
  next_cursor: string | null;
  total_returned: number;
}

export interface LinksState {
  links: Link[];
  nextCursor: string | null;
  hasMore: boolean;
  syncStatus: RequestStatus;
  networkStatus: NetworkStatus;
  entities: Entity[];
  error: string | null;
  isLoadingLinks: boolean;
  isLoadingEntities: boolean;
  
  // Actions
  setNetworkStatus: (status: NetworkStatus) => void;
  fetchEntities: () => Promise<void>;
  fetchLinks: (reset?: boolean) => Promise<void>;
  syncLink: (token: string, entityBId: string, privateNotes?: string) => Promise<void>;
  clearError: () => void;
  addEntityLocally: (label: string) => Promise<Entity>;
}

export const useLinksStore = create<LinksState>((set, get) => ({
  links: [],
  nextCursor: null,
  hasMore: true,
  syncStatus: 'idle',
  networkStatus: 'online',
  entities: [],
  error: null,
  isLoadingLinks: false,
  isLoadingEntities: false,

  setNetworkStatus: (status) => set({ networkStatus: status }),

  clearError: () => set({ error: null, syncStatus: 'idle' }),

  fetchEntities: async () => {
    set({ isLoadingEntities: true, error: null });
    try {
      const entities = await apiFetch<Entity[]>('/api/entities');
      set({ entities, isLoadingEntities: false });
    } catch (err: any) {
      set({
        error: err.data?.detail || err.message || 'Failed to fetch entities',
        isLoadingEntities: false
      });
    }
  },

  addEntityLocally: async (label: string) => {
    try {
      const newEntity = await apiFetch<Entity>('/api/entities', {
        method: 'POST',
        body: JSON.stringify({ label })
      });
      set(state => ({ entities: [newEntity, ...state.entities] }));
      return newEntity;
    } catch (err: any) {
      const errMsg = err.data?.detail || err.message || 'Failed to create entity';
      set({ error: errMsg });
      throw err;
    }
  },

  fetchLinks: async (reset = false) => {
    if (get().isLoadingLinks) return;
    
    set({ isLoadingLinks: true, error: null });
    const cursor = reset ? null : get().nextCursor;
    
    try {
      const path = `/api/state/links?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await apiFetch<CursorPageResponse>(path);
      
      set(state => ({
        links: reset ? response.items : [...state.links, ...response.items],
        nextCursor: response.next_cursor,
        hasMore: response.next_cursor !== null,
        isLoadingLinks: false
      }));
    } catch (err: any) {
      set({
        error: err.data?.detail || err.message || 'Failed to load links directory',
        isLoadingLinks: false
      });
    }
  },

  syncLink: async (token, entityBId, privateNotes) => {
    const optimisticId = `temp-${Date.now()}`;
    const currentRole = localStorage.getItem('vertex_role') || 'user';
    const entities = get().entities;
    const entityB = entities.find(e => e.id === entityBId);

    // Build immediate optimistic UI link item representation
    const tempEntityA: Entity = {
      id: 'resolving',
      label: 'Resolving opaque entity...',
      owner_role: 'user',
      created_at: new Date().toISOString()
    };

    const optimisticLink: Link = {
      id: optimisticId,
      entity_a_id: 'resolving',
      entity_b_id: entityBId,
      private_notes: currentRole === 'admin' ? null : (privateNotes || null),
      created_at: new Date().toISOString(),
      entity_a: tempEntityA,
      entity_b: entityB || {
        id: entityBId,
        label: 'Selected Entity',
        owner_role: 'user',
        created_at: new Date().toISOString()
      }
    };

    const previousLinks = [...get().links];

    // Transition state to optimistic immediately
    set({
      links: [optimisticLink, ...previousLinks],
      syncStatus: 'optimistic',
      error: null
    });

    try {
      // API call executes (supports client-side retries via fetch configuration)
      const response = await apiFetch<Link & { created: boolean }>('/api/state/sync', {
        method: 'POST',
        body: JSON.stringify({
          token,
          entity_b_id: entityBId,
          private_notes: privateNotes
        })
      });

      // Replace optimistic placeholder with confirmed server payload
      set(state => ({
        links: state.links.map(item => 
          item.id === optimisticId ? {
            id: response.id,
            entity_a_id: response.entity_a_id,
            entity_b_id: response.entity_b_id,
            private_notes: response.private_notes,
            created_at: response.created_at,
            entity_a: response.entity_a,
            entity_b: response.entity_b
          } : item
        ),
        syncStatus: 'confirmed'
      }));
    } catch (err: any) {
      // Reconcile list: Rollback optimistic addition on error
      set({
        links: previousLinks,
        syncStatus: 'error',
        error: err.data?.detail || err.message || 'Synchronization failed'
      });
      throw err;
    }
  }
}));
