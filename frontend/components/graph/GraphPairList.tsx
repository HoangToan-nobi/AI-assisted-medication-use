import AlertCard from "@/components/AlertCard";
import MaterialIcon from "@/components/MaterialIcon";
import type { Severity } from "@/lib/api";

export type GraphPairItem = {
  id: string;
  thuocA: string;
  thuocB: string;
  severity?: Severity;
  description: string;
  source: string;
  hasIncompletePair?: boolean;
  // Gợi ý xử trí dành cho dược sĩ (xu_tri) - chỉ có khi xem qua luồng dược sĩ,
  // backend đã tự ẩn field này với bệnh nhân nên phía trên luôn là undefined.
  management?: string;
  // Mô tả khoa học nguyên văn từ CSDL (mo_ta) - cũng chỉ dược sĩ mới thấy.
  scientificDescription?: string;
};

type GraphPairListProps = {
  items: GraphPairItem[];
  onViewDetail?: (id: string) => void;
  // Mở lại popup gợi ý nhờ dược sĩ xác nhận (nếu người dùng đã lỡ đóng nó) - chỉ
  // hiện nút này trên thẻ có mức độ nghiêm trọng.
  onReopenSeverePopup?: () => void;
};

export default function GraphPairList({ items, onViewDetail, onReopenSeverePopup }: GraphPairListProps) {
  return (
    <div className="interaction-pairs">
      {items.map((item) => (
        <div className="interaction-pair-card" id={`interaction-pair-${item.id}`} key={item.id}>
          {(onViewDetail || (item.severity === "nang" && onReopenSeverePopup)) && (
            <div className="tt-graph-pair__actions">
              {item.severity === "nang" && onReopenSeverePopup && (
                <button type="button" className="tt-graph-pair__severe" onClick={onReopenSeverePopup} title="Nhờ dược sĩ xác nhận tương tác này">
                  <MaterialIcon name="local_pharmacy" size={16} /> Nhờ dược sĩ
                </button>
              )}
              {onViewDetail && (
                <button type="button" className="tt-graph-pair__detail" onClick={() => onViewDetail(item.id)}>
                  <MaterialIcon name="visibility" size={16} /> Xem chi tiết
                </button>
              )}
            </div>
          )}
          <AlertCard
            thuocA={item.thuocA} thuocB={item.thuocB} severity={item.severity} description={item.description} source={item.source}
            management={item.management} scientificDescription={item.scientificDescription}
          />
          {item.hasIncompletePair && (
            <p className="tt-graph-pair__notice"><MaterialIcon name="info" size={15} /> Còn cặp chưa được phân loại mức độ trong nhóm này.</p>
          )}
        </div>
      ))}
    </div>
  );
}
