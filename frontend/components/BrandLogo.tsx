import MaterialIcon from "@/components/MaterialIcon";
import { brand } from "@/lib/design-system";

type BrandLogoProps = {
  size?: "sm" | "md" | "lg";
  showTagline?: boolean;
  className?: string;
};

export default function BrandLogo({ size = "md", showTagline = false, className = "" }: BrandLogoProps) {
  return (
    <div className={`brand-logo brand-logo--${size} ${className}`} style={{ display: "flex", flexDirection: "row", flexWrap: "nowrap", alignItems: "center", gap: "8px" }}>
      <div className="brand-logo__mark" style={{ display: "flex", alignItems: "center", color: "#1a2b4c" }}>
        <MaterialIcon name="clinical_notes" size={size === "lg" ? 32 : size === "sm" ? 22 : 28} filled />
      </div>
      <div className="brand-logo__text" style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <span className="brand-logo__name" style={{ fontWeight: 800, color: "#1a2b4c", fontSize: size === "lg" ? "24px" : size === "sm" ? "18px" : "20px", whiteSpace: "nowrap" }}>{brand.productName}</span>
        {showTagline && <span className="brand-logo__tagline" style={{ fontSize: "12px", color: "#666", whiteSpace: "nowrap" }}>{brand.tagline}</span>}
      </div>
    </div>
  );
}
