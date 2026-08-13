import MaterialIcon from "@/components/MaterialIcon";
import { brand } from "@/lib/design-system";

type BrandLogoProps = {
  size?: "sm" | "md" | "lg";
  showTagline?: boolean;
  className?: string;
};

export default function BrandLogo({ size = "md", showTagline = false, className = "" }: BrandLogoProps) {
  return (
    <div className={`brand-logo brand-logo--${size} ${className}`}>
      <div className="brand-logo__mark">
        <MaterialIcon name="clinical_notes" size={size === "lg" ? 32 : size === "sm" ? 20 : 28} filled />
      </div>
      <div className="brand-logo__text">
        <span className="brand-logo__name">{brand.productName}</span>
        {showTagline && <span className="brand-logo__tagline">{brand.tagline}</span>}
      </div>
    </div>
  );
}
