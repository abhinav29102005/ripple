export interface TaskLike {
  id: string;
  status: 'queued' | 'claimed' | 'done' | 'failed';
}

export function groupTasksByStatus<T extends TaskLike>(tasks: T[]) {
  return {
    queued: tasks.filter((t) => t.status === 'queued'),
    claimed: tasks.filter((t) => t.status === 'claimed'),
    done: tasks.filter((t) => t.status === 'done'),
    failed: tasks.filter((t) => t.status === 'failed'),
  };
}
