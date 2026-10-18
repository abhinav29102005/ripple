import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { Clock, CheckCircle, Layers, UserCheck } from 'lucide-react';
import type { Task } from '../../api/types';

export const CoordinationTab: React.FC = () => {
  const { data: tasksData } = useQuery({
    queryKey: ['tasks'],
    queryFn: api.getTasks,
    refetchInterval: 1000,
  });

  const { data: agentsData } = useQuery({
    queryKey: ['agents'],
    queryFn: api.getAgents,
    refetchInterval: 2000,
  });

  const tasks = tasksData?.tasks || [];
  const agents = agentsData?.agents || [];

  const queued = tasks.filter((t) => t.status === 'queued');
  const claimed = tasks.filter((t) => t.status === 'claimed');
  const done = tasks.filter((t) => t.status === 'done');
  const failed = tasks.filter((t) => t.status === 'failed');

  return (
    <div className="h-full flex flex-col p-3 overflow-hidden bg-surface select-none">
      <div className="grid grid-cols-4 gap-3 flex-1 min-h-0">
        {/* Queued */}
        <div className="flex flex-col rounded border border-border bg-bg overflow-hidden">
          <div className="px-2.5 py-1.5 border-b border-border bg-raised flex items-center justify-between text-xs">
            <span className="font-semibold text-secondary flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-muted" />
              <span>Queued</span>
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-bg text-secondary border border-border">
              {queued.length}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {queued.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
            {queued.length === 0 && (
              <div className="text-center text-[11px] text-muted py-6">No tasks queued</div>
            )}
          </div>
        </div>

        {/* Claimed */}
        <div className="flex flex-col rounded border border-border bg-bg overflow-hidden">
          <div className="px-2.5 py-1.5 border-b border-border bg-raised flex items-center justify-between text-xs">
            <span className="font-semibold text-secondary flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-accent" />
              <span>Claimed (Active Lease)</span>
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-bg text-accent border border-accent/30">
              {claimed.length}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {claimed.map((task) => (
              <TaskCard key={task.id} task={task} showLease />
            ))}
            {claimed.length === 0 && (
              <div className="text-center text-[11px] text-muted py-6">No active claims</div>
            )}
          </div>
        </div>

        {/* Done */}
        <div className="flex flex-col rounded border border-border bg-bg overflow-hidden">
          <div className="px-2.5 py-1.5 border-b border-border bg-raised flex items-center justify-between text-xs">
            <span className="font-semibold text-secondary flex items-center gap-1.5">
              <CheckCircle className="w-3.5 h-3.5 text-ok-green" />
              <span>Completed</span>
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-bg text-ok-green border border-ok-green/30">
              {done.length}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {done.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
            {done.length === 0 && (
              <div className="text-center text-[11px] text-muted py-6">No completed tasks</div>
            )}
          </div>
        </div>

        {/* Failed / Agents */}
        <div className="flex flex-col rounded border border-border bg-bg overflow-hidden">
          <div className="px-2.5 py-1.5 border-b border-border bg-raised flex items-center justify-between text-xs">
            <span className="font-semibold text-secondary flex items-center gap-1.5">
              <UserCheck className="w-3.5 h-3.5 text-secondary" />
              <span>Registered Workers</span>
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-bg text-secondary border border-border">
              {agents.length}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {failed.length > 0 && (
              <div className="mb-2 pb-2 border-b border-border">
                <span className="text-[10px] text-retraction-red font-mono font-semibold block mb-1">
                  Failed Tasks ({failed.length}):
                </span>
                {failed.map((t) => (
                  <TaskCard key={t.id} task={t} />
                ))}
              </div>
            )}

            {agents.map((agent) => (
              <div key={agent.id} className="p-2 rounded bg-surface border border-border text-[11px]">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-text font-semibold">{agent.id}</span>
                  <span className="text-[9px] px-1 py-0.2 rounded bg-ok-green/15 text-ok-green border border-ok-green/30">
                    {agent.status}
                  </span>
                </div>
                <div className="text-muted flex items-center justify-between text-[10px]">
                  <span>Role: {agent.role}</span>
                  <span className="font-mono">task: {agent.task_type}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const TaskCard: React.FC<{ task: Task; showLease?: boolean }> = ({ task, showLease }) => {
  return (
    <div className="p-2 rounded bg-surface border border-border text-[11px] font-mono">
      <div className="flex items-center justify-between gap-1 mb-1">
        <span className="text-text font-semibold truncate max-w-[140px]" title={task.key}>
          {task.key}
        </span>
        <span className="text-[9px] px-1 py-0.2 rounded bg-raised border border-border text-secondary">
          {task.type}
        </span>
      </div>

      <div className="flex items-center justify-between text-[10px] text-muted">
        <span>pri: {task.priority}</span>
        {task.claimed_by && <span className="text-accent truncate max-w-[100px]">{task.claimed_by}</span>}
      </div>

      {showLease && task.lease_until > 0 && (
        <div className="mt-1.5 pt-1 border-t border-border/50">
          <div className="w-full bg-raised rounded-full h-1 overflow-hidden">
            <div className="bg-accent h-full w-2/3 animate-pulse" />
          </div>
          <span className="text-[9px] text-muted block mt-0.5">Lease expires in 25s</span>
        </div>
      )}
    </div>
  );
};
