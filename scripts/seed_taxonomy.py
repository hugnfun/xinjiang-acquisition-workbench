import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sidecar.db.session import init_db, get_session
from sidecar.db.models import TagDimension, TagValue

TAXONOMY = {
    "content_type": ("内容类型", ["风景震撼", "避坑攻略", "价格透明", "行程方案", "小众秘境", "情绪价值"]),
    "season": ("出行季节", ["春", "夏", "秋", "冬", "不限"]),
    "audience": ("目标受众", ["亲子", "情侣", "闺蜜", "独行", "中年", "摄影爱好者", "不限"]),
    "route": ("路线区域", ["北疆", "南疆", "伊犁", "喀纳斯", "独库公路", "赛里木湖", "其他"]),
    "price": ("价格区间", ["低价", "中端", "高端", "未提及"]),
    "emotion": ("情绪类型", ["震撼", "治愈", "避坑警示", "向往", "吐槽", "其他"]),
}

def seed_taxonomy():
    init_db()
    s = get_session()
    for name, (desc, values) in TAXONOMY.items():
        d = s.query(TagDimension).filter_by(name=name).first()
        if d is None:
            d = TagDimension(name=name, description=desc)
            s.add(d); s.flush()
        existing = {v.value for v in d.values}
        for v in values:
            if v not in existing:
                s.add(TagValue(dimension_id=d.id, value=v, alias=[]))
    s.commit()

if __name__ == "__main__":
    seed_taxonomy()
    print("标签体系初始化完成")
