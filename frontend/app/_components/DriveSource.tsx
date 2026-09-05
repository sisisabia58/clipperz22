import { HardDrive, Loader2, RefreshCw } from "lucide-react";
import type { DriveFile, DriveStatus } from "../../lib/apiClient";

type DriveSourceProps = {
  status: DriveStatus | null;
  files: DriveFile[];
  folders: DriveFile[];
  selectedFileId: string;
  selectedFolderId: string;
  autoUpload: boolean;
  isLoading: boolean;
  isConnecting: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onRefresh: () => void;
  onSelectFile: (fileId: string) => void;
  onSelectFolder: (folderId: string, folderName: string) => void;
  onAutoUploadChange: (value: boolean) => void;
};

export function DriveSource({
  status,
  files,
  folders,
  selectedFileId,
  selectedFolderId,
  autoUpload,
  isLoading,
  isConnecting,
  onConnect,
  onDisconnect,
  onRefresh,
  onSelectFile,
  onSelectFolder,
  onAutoUploadChange,
}: DriveSourceProps) {
  if (!status?.configured) {
    return (
      <div className="driveBlock">
        <p className="field-help">
          Set <code>GOOGLE_CLIENT_ID</code> and <code>GOOGLE_CLIENT_SECRET</code> on the backend, then
          restart ClipForge to connect Google Drive.
        </p>
      </div>
    );
  }

  if (!status.connected) {
    return (
      <div className="driveBlock">
        <p className="field-help">Connect Google Drive to pick a video and optionally save clips back to a folder.</p>
        <button className="primary" type="button" onClick={onConnect} disabled={isConnecting}>
          {isConnecting ? <Loader2 className="spin" size={16} /> : <HardDrive size={16} />}
          Connect Google Drive
        </button>
      </div>
    );
  }

  const selectedFolder = folders.find((folder) => folder.id === selectedFolderId);

  return (
    <div className="driveBlock">
      <div className="driveAccount">
        <p className="field-help">Connected as {status.email || "Google Drive"}</p>
        <div className="driveAccountActions">
          <button className="ghostButton" type="button" onClick={onRefresh} disabled={isLoading} title="Refresh files">
            <RefreshCw size={14} className={isLoading ? "spin" : undefined} />
            Refresh
          </button>
          <button className="ghostButton" type="button" onClick={onDisconnect}>
            Disconnect
          </button>
        </div>
      </div>

      <div className="driveList" role="listbox" aria-label="Google Drive videos">
        {isLoading && !files.length ? (
          <p className="field-help">Loading videos...</p>
        ) : files.length ? (
          files.map((file) => (
            <button
              key={file.id}
              type="button"
              className={file.id === selectedFileId ? "driveRow selected" : "driveRow"}
              onClick={() => onSelectFile(file.id)}
            >
              <span className="driveRowName">{file.name}</span>
            </button>
          ))
        ) : (
          <p className="field-help">No videos found in Drive.</p>
        )}
      </div>
      <p className="field-help">
        {selectedFileId ? "Video selected. Start clipping when you are ready." : "Select a video to clip."}
      </p>

      <label className="check">
        <input
          type="checkbox"
          checked={autoUpload}
          onChange={(event) => onAutoUploadChange(event.target.checked)}
        />
        Auto-upload finished clips to a Drive folder
      </label>

      {autoUpload ? (
        <label className="field">
          <span>Destination folder</span>
          <select
            className="fontSelect"
            value={selectedFolderId}
            onChange={(event) => {
              const folder = folders.find((item) => item.id === event.target.value);
              onSelectFolder(event.target.value, folder?.name || "");
            }}
          >
            <option value="">Select a folder</option>
            {folders.map((folder) => (
              <option key={folder.id} value={folder.id}>
                {folder.name}
              </option>
            ))}
          </select>
          <p className="field-help">
            {selectedFolder
              ? `Clips stay on this machine and are copied to “${selectedFolder.name}”.`
              : "Choose the Drive folder that should receive the finished clips."}
          </p>
        </label>
      ) : (
        <p className="field-help">Clips will be saved locally only unless you enable Drive upload.</p>
      )}
    </div>
  );
}
