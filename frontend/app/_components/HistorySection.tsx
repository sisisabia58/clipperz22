import { Trash2 } from "lucide-react";
import { statusCopy, statusIcon } from "../../lib/constants";
import type { ClipJob } from "../../types/clip.type";

type HistorySectionProps = {
  jobs: ClipJob[];
  onDeleteAll: () => void;
  onSelectJob: (job: ClipJob) => void;
};

export function HistorySection({ jobs, onDeleteAll, onSelectJob }: HistorySectionProps) {
  return (
    <section className="history">
      <div className="sectionHeader">
        <h2>Riwayat Proses</h2>
        <div className="historyActions">
          <span className="sectionBadge">{jobs.length} total</span>
          {jobs.length > 0 ? (
            <button
              type="button"
              onClick={onDeleteAll}
              className="iconButton dangerIconButton"
              title="Hapus Semua Riwayat"
            >
              <Trash2 size={16} />
            </button>
          ) : null}
        </div>
      </div>

      <div className="jobList">
        {jobs.map((item) => {
          const Icon = statusIcon[item.status];
          const count = item.clips.length ? `${item.clips.length} klip` : `${item.candidates.length} kandidat`;

          return (
            <button className="jobRow" type="button" key={item.id} onClick={() => onSelectJob(item)}>
              <div className={`jobRow-status status-${item.status}`}>
                <Icon className={item.status === "running" ? "spin" : ""} size={18} />
              </div>
              <span>{statusCopy[item.status]}</span>
              <strong>{count}</strong>
            </button>
          );
        })}
      </div>
    </section>
  );
}
