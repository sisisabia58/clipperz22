import { Coffee, Heart } from "lucide-react";

export function SiteFooter() {
  return (
    <footer className="siteFooter">
      <p>
        Open-source project by{" "}
        <a href="https://mallexibra.my.id/" target="_blank" rel="noreferrer">
          Mallexibra
        </a>
        <Heart size={14} aria-hidden="true" />
      </p>
      <a className="donationLink" href="https://saweria.co/mallexibra" target="_blank" rel="noreferrer">
        <Coffee size={16} aria-hidden="true" />
        Buy me a coffee
      </a>
    </footer>
  );
}
