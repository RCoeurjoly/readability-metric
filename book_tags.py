"""Tag books from known external/canonical ranking lists."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable


CHINESE_NOVEL_20C_TOP100 = [
    (1, "呐喊", "鲁迅"),
    (2, "边城", "沈从文"),
    (3, "骆驼祥子", "老舍"),
    (4, "传奇", "张爱玲"),
    (5, "围城", "錢鍾書"),
    (6, "子夜", "茅盾"),
    (7, "台北人", "白先勇"),
    (8, "家", "巴金"),
    (9, "呼兰河传", "萧红"),
    (10, "老残游记", "刘鹗"),
    (11, "寒夜", "巴金"),
    (12, "彷徨", "鲁迅"),
    (13, "官场现形记", "李伯元"),
    (14, "财主底儿女们", "路翎"),
    (15, "将军族", "陈映真"),
    (16, "沉沦", "郁达夫"),
    (17, "死水微澜", "李劼人"),
    (18, "红高粱", "莫言"),
    (19, "小二黑结婚", "赵树理"),
    (20, "棋王", "鍾阿城"),
    (21, "家變", "王文兴"),
    (22, "马桥词典", "韩少功"),
    (23, "亚细亚的孤儿", "吴浊流"),
    (24, "半生缘", "张爱玲"),
    (25, "四世同堂", "老舍"),
    (26, "胡雪巖", "高阳"),
    (27, "啼笑因缘", "张恨水"),
    (28, "儿子的大玩偶", "黄春明"),
    (29, "射雕英雄传", "金庸"),
    (30, "莎菲女士的日记", "丁玲"),
    (31, "鹿鼎记", "金庸"),
    (32, "孽海花", "曾朴"),
    (33, "惹事", "赖和"),
    (34, "嫁妆一牛车", "王祯和"),
    (35, "异域", "柏杨"),
    (36, "曾国藩", "唐浩明"),
    (37, "原乡人", "锺理和"),
    (38, "白鹿原", "陈忠实"),
    (39, "长恨歌", "王安忆"),
    (40, "吉陵春秋", "李永平"),
    (41, "黄祸", "王力雄"),
    (42, "狂风沙", "司马中原"),
    (43, "艳阳天", "浩然"),
    (44, "公墓", "穆时英"),
    (45, "旧址", "李锐"),
    (46, "星星·月亮·太阳", "徐速"),
    (47, "台湾人三部曲", "锺肇政"),
    (48, "洗澡", "杨绛"),
    (49, "旋风", "姜贵"),
    (50, "荷花淀", "孙犁"),
    (51, "我城", "西西"),
    (52, "受戒", "汪曾祺"),
    (53, "铁浆", "朱西甯"),
    (54, "世纪末的华丽", "朱天文"),
    (55, "蜀山剑侠传", "还珠楼主"),
    (56, "又见棕榈，又见棕榈", "于梨华"),
    (57, "浮躁", "贾平凹"),
    (58, "组织部新来的年轻人", "王蒙"),
    (59, "玉梨魂", "徐枕亚"),
    (60, "香港三部曲", "施叔青"),
    (61, "京华烟云", "林语堂"),
    (62, "倪焕之", "叶圣陶"),
    (63, "春桃", "许地山"),
    (64, "桑青与桃红", "聂华苓"),
    (65, "蓝与黑", "王蓝"),
    (66, "二月", "柔石"),
    (67, "风萧萧", "徐訏"),
    (68, "芙蓉镇", "古华"),
    (69, "地之子", "臺静農"),
    (70, "城南旧事", "林海音"),
    (71, "古船", "张炜"),
    (72, "酒徒", "刘以鬯"),
    (73, "未央歌", "鹿桥"),
    (74, "沉重的翅膀", "张洁"),
    (75, "果园城记", "师陀"),
    (76, "人啊，人！", "戴厚英"),
    (77, "黄金时代", "王小波"),
    (78, "狗日的粮食", "刘恒"),
    (79, "棋王", "张系国"),
    (80, "赖索", "黄凡"),
    (81, "妻妾成群", "苏童"),
    (82, "霸王别姬", "李碧华"),
    (83, "杀夫", "李昂"),
    (84, "楚留香", "古龙"),
    (85, "窗外", "琼瑶"),
    (86, "沉默之岛", "苏伟贞"),
    (87, "白发魔女传", "梁羽生"),
    (88, "古都", "朱天心"),
    (89, "尹县长", "陈若曦"),
    (90, "四喜忧国", "张大春"),
    (91, "喜寶", "亦舒"),
    (92, "男人的一半是女人", "张贤亮"),
    (93, "将军底头", "施蛰存"),
    (94, "蓝血人", "倪匡"),
    (95, "二十年目睹之怪现状", "吴趼人"),
    (96, "活著", "余华"),
    (97, "冈底斯的诱惑", "马原"),
    (98, "十年十意", "林斤澜"),
    (99, "北极风情画", "无名氏"),
    (100, "雍正皇帝", "二月河"),
]

# Small, explicit variant map for common simplified/traditional differences in the list.
# This is deliberately conservative; ambiguous matches still require exact title+author or unique title.
CHAR_VARIANTS = str.maketrans(
    {
        "呐": "吶", "爱": "愛", "边": "邊", "骆": "駱", "驼": "駝", "祥": "祥", "张": "張",
        "钱": "錢", "钟": "鍾", "书": "書", "兰": "蘭", "萧": "蕭", "残": "殘",
        "刘": "劉", "鹗": "鶚", "场": "場", "现": "現", "记": "記", "将": "將",
        "军": "軍", "陈": "陳", "郁": "郁", "澜": "瀾", "红": "紅", "赵": "趙",
        "树": "樹", "马": "馬", "词": "詞", "韩": "韓", "细": "細", "缘": "緣",
        "阳": "陽", "啼": "啼", "妆": "妝", "异": "異", "国": "國", "藩": "藩",
        "乡": "鄉", "锺": "鍾", "诚": "誠", "长": "長", "旧": "舊", "锐": "銳",
        "星": "星", "湾": "灣", "杨": "楊", "绛": "絳", "孙": "孫", "铁": "鐵",
        "浆": "漿", "华": "華", "侠": "俠", "传": "傳", "还": "還", "见": "見",
        "梨": "梨", "贾": "賈", "凹": "凹", "轻": "輕", "云": "雲",
        "语": "語", "叶": "葉", "圣": "聖", "聂": "聶", "蓝": "藍", "风": "風",
        "镇": "鎮", "静": "靜", "农": "農", "旧": "舊", "张": "張", "洁": "潔",
        "师": "師", "粮": "糧", "苏": "蘇", "杀": "殺", "岛": "島", "县": "縣",
        "忧": "憂", "宝": "寶", "贤": "賢", "蛰": "蟄", "血": "血", "趼": "趼",
        "著": "著", "诱": "誘", "极": "極", "画": "畫", "雍": "雍", "悦": "悅",
    }
)

LIST_ID = "20c_chinese_novel_top100"
LIST_NAME = "20世纪中文小说100强"
SOURCE_URL = "https://zh.wikipedia.org/wiki/20%E4%B8%96%E7%BA%AA%E4%B8%AD%E6%96%87%E5%B0%8F%E8%AF%B4100%E5%BC%BA"


def normalize(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).strip().translate(CHAR_VARIANTS)
    value = re.sub(r"[\s　《》〈〉·．.。!！?？,，、:：;；()（）\[\]【】\-—_]+", "", value)
    return value.casefold()


def canonical_entries() -> list[dict]:
    return [
        {
            "list_id": LIST_ID,
            "list_name": LIST_NAME,
            "source_url": SOURCE_URL,
            "rank": rank,
            "title": title,
            "creator": creator,
            "normalized_title": normalize(title),
            "normalized_creator": normalize(creator),
        }
        for rank, title, creator in CHINESE_NOVEL_20C_TOP100
    ]



def list_id_from_filename(filename: str) -> str:
    return Path(filename).stem


def load_ranking_json_entries(json_dir: Path) -> list[dict]:
    entries: list[dict] = []
    for path in sorted(json_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        list_id = list_id_from_filename(path.name)
        list_name = data.get("榜单名称") or list_id
        source_url = data.get("URL")
        for index, item in enumerate(data.get("条目", []), start=1):
            title = item.get("书名")
            creator = item.get("作者") or item.get("原作者")
            if not title:
                continue
            rank = item.get("rank_position")
            entries.append(
                {
                    "list_id": list_id,
                    "list_name": list_name,
                    "source_url": source_url,
                    "rank": int(rank) if isinstance(rank, int) else index,
                    "rank_position": rank,
                    "title": title,
                    "creator": creator,
                    "publisher": item.get("出版社"),
                    "publication_year": item.get("出版年"),
                    "note": item.get("简短说明/注释"),
                    "normalized_title": normalize(title),
                    "normalized_creator": normalize(creator),
                }
            )
    return entries


def all_catalog_entries(ranking_json_dir: Path | None = None, include_top100: bool = True) -> list[dict]:
    entries = []
    if include_top100:
        entries.extend(canonical_entries())
    if ranking_json_dir:
        entries.extend(load_ranking_json_entries(ranking_json_dir))
    return entries

def load_manifest(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def match_books(manifest_rows: list[dict], entries: list[dict]) -> list[dict]:
    canonical_title_counts: dict[str, int] = {}
    for entry in entries:
        canonical_title_counts[entry["normalized_title"]] = canonical_title_counts.get(entry["normalized_title"], 0) + 1

    by_title_creator: dict[tuple[str, str], list[dict]] = {}
    by_title: dict[str, list[dict]] = {}
    for row in manifest_rows:
        title = normalize(row.get("title"))
        creator = normalize(row.get("creator"))
        by_title_creator.setdefault((title, creator), []).append(row)
        by_title.setdefault(title, []).append(row)

    matches = []
    seen: set[tuple[str, int]] = set()
    for entry in entries:
        candidates = by_title_creator.get((entry["normalized_title"], entry["normalized_creator"]), [])
        match_type = "title_creator_exact"
        if not candidates and canonical_title_counts.get(entry["normalized_title"], 0) == 1:
            title_candidates = by_title.get(entry["normalized_title"], [])
            if len(title_candidates) == 1:
                candidates = title_candidates
                match_type = "unique_title_exact"
        for row in candidates:
            key = (str(row.get("book_id")), int(entry["rank"]))
            if key in seen:
                continue
            seen.add(key)
            matches.append(
                {
                    "book_id": row.get("book_id"),
                    "title": row.get("title"),
                    "creator": row.get("creator"),
                    "filename": row.get("filename"),
                    "filepath": row.get("filepath"),
                    "book_dir": row.get("book_dir"),
                    "tags": [
                        {
                            "list_id": entry["list_id"],
                            "list_name": entry["list_name"],
                            "source_url": entry["source_url"],
                            "rank": entry["rank"],
                            "canonical_title": entry["title"],
                            "canonical_creator": entry["creator"],
                            "match_type": match_type,
                            "rank_position": entry.get("rank_position", entry["rank"]),
                            "publisher": entry.get("publisher"),
                            "publication_year": entry.get("publication_year"),
                            "note": entry.get("note"),
                        }
                    ],
                }
            )
    matches.sort(key=lambda row: row["tags"][0]["rank"])
    return matches


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_catalog(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tag book manifest entries with known external ranking lists.")
    parser.add_argument("--manifest", default="results/zh-books/manifest.jsonl")
    parser.add_argument("--output", default="results/book-tags.jsonl")
    parser.add_argument("--catalog-output", default="results/book-tag-catalog.json")
    parser.add_argument("--ranking-json-dir", help="Directory of ranking JSON files to include")
    parser.add_argument("--no-top100", action="store_true", help="Do not include built-in 20th-century Chinese novel top 100 list")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    entries = all_catalog_entries(
        Path(args.ranking_json_dir) if args.ranking_json_dir else None,
        include_top100=not args.no_top100,
    )
    rows = load_manifest(Path(args.manifest))
    matches = match_books(rows, entries)
    write_jsonl(Path(args.output), matches)
    write_catalog(Path(args.catalog_output), entries)
    print(f"Wrote {len(matches)} tagged book matches to {args.output}")
    print(f"Wrote canonical list catalog to {args.catalog_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
