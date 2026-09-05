import toast from "react-hot-toast";

type DeleteAllToastProps = {
  onConfirm: () => Promise<void>;
  toastId: string;
};

export function DeleteAllToast({ onConfirm, toastId }: DeleteAllToastProps) {
  return (
    <div className="confirmToast">
      <div className="confirmToast-copy">
        <strong>Hapus seluruh riwayat dan output?</strong>
        <p>Semua job dan file video di folder outputs akan dihapus.</p>
      </div>
      <div className="confirmToast-actions">
        <button className="ghostButton" type="button" onClick={() => toast.dismiss(toastId)}>
          Batal
        </button>
        <button
          className="dangerButton"
          type="button"
          onClick={async () => {
            toast.dismiss(toastId);
            await onConfirm();
          }}
        >
          Hapus Semua
        </button>
      </div>
    </div>
  );
}
