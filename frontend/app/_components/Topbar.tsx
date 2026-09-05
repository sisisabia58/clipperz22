import { RefreshCw } from "lucide-react";

type TopbarProps = {
  onRefresh: () => void;
};

export function Topbar({ onRefresh }: TopbarProps) {
  return (
    <section className="topbar">
      <div className="topbar-brand">
        <img className="brandMark" src="/logo.svg" alt="" aria-hidden="true" />
        <div className="brandCopy">
          <h1 className="logo-text">ClipForge</h1>
          <p className="tagline">Turn long videos into ready-to-post clips.</p>
        </div>
      </div>
      <button className="iconButton" type="button" onClick={onRefresh} title="Refresh data">
        <RefreshCw size={18} />
      </button>
    </section>
  );
}
