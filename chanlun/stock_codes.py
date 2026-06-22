# chanlun/stock_codes.py
# 股票代码库 - A股核心股票代码 + 名称，支持搜索
# 覆盖银行、保险、证券、白酒、消费、医药、科技、新能源、房地产、基建等主要板块
from typing import List, Optional

CODE_LIST = [
    {"code": "000001", "name": "平安银行", "sector": "银行"},
    {"code": "000002", "name": "万科A",    "sector": "房地产"},
    {"code": "000333", "name": "美的集团", "sector": "家电"},
    {"code": "000568", "name": "泸州老窖", "sector": "白酒"},
    {"code": "000651", "name": "格力电器", "sector": "家电"},
    {"code": "000725", "name": "京东方A", "sector": "电子"},
    {"code": "000858", "name": "五粮液",   "sector": "白酒"},
    {"code": "002415", "name": "海康威视", "sector": "安防"},
    {"code": "002475", "name": "立讯精密", "sector": "电子"},
    {"code": "002594", "name": "比亚迪",   "sector": "新能源汽车"},
    {"code": "300750", "name": "宁德时代", "sector": "锂电池"},
    {"code": "300059", "name": "东方财富", "sector": "证券"},
    {"code": "600000", "name": "浦发银行", "sector": "银行"},
    {"code": "600030", "name": "中信证券", "sector": "证券"},
    {"code": "600036", "name": "招商银行", "sector": "银行"},
    {"code": "600048", "name": "保利发展", "sector": "房地产"},
    {"code": "600276", "name": "恒瑞医药", "sector": "医药"},
    {"code": "600309", "name": "万华化学", "sector": "化工"},
    {"code": "600519", "name": "贵州茅台", "sector": "白酒"},
    {"code": "600585", "name": "海螺水泥", "sector": "建材"},
    {"code": "600660", "name": "福耀玻璃", "sector": "汽车零部件"},
    {"code": "600690", "name": "海尔智家", "sector": "家电"},
    {"code": "600887", "name": "伊利股份", "sector": "食品"},
    {"code": "600900", "name": "长江电力", "sector": "电力"},
    {"code": "601012", "name": "隆基绿能", "sector": "光伏"},
    {"code": "601088", "name": "中国神华", "sector": "煤炭"},
    {"code": "601166", "name": "兴业银行", "sector": "银行"},
    {"code": "601288", "name": "农业银行", "sector": "银行"},
    {"code": "601318", "name": "中国平安", "sector": "保险"},
    {"code": "601336", "name": "新华保险", "sector": "保险"},
    {"code": "601398", "name": "工商银行", "sector": "银行"},
    {"code": "601628", "name": "中国人寿", "sector": "保险"},
    {"code": "601668", "name": "中国建筑", "sector": "基建"},
    {"code": "601688", "name": "华泰证券", "sector": "证券"},
    {"code": "601766", "name": "中国中车", "sector": "高端装备"},
    {"code": "601857", "name": "中国石油", "sector": "石油"},
    {"code": "601888", "name": "中国中免", "sector": "消费"},
    {"code": "601899", "name": "紫金矿业", "sector": "有色"},
    {"code": "601988", "name": "中国银行", "sector": "银行"},
    {"code": "601998", "name": "中信银行", "sector": "银行"},
    {"code": "603288", "name": "海天味业", "sector": "食品"},
    {"code": "603501", "name": "韦尔股份", "sector": "半导体"},
    {"code": "603986", "name": "兆易创新", "sector": "半导体"},
    {"code": "688981", "name": "中芯国际", "sector": "半导体"},
    {"code": "688036", "name": "传音控股", "sector": "消费电子"},
    {"code": "688169", "name": "石头科技", "sector": "家电"},
    {"code": "601138", "name": "工业富联", "sector": "电子代工"},
    {"code": "600031", "name": "三一重工", "sector": "工程机械"},
    {"code": "600406", "name": "国电南瑞", "sector": "电力设备"},
    {"code": "002714", "name": "牧原股份", "sector": "农业"},
    {"code": "000063", "name": "中兴通讯", "sector": "通信"},
    {"code": "000725", "name": "京东方A", "sector": "显示面板"},
    {"code": "002241", "name": "歌尔股份", "sector": "电子"},
    {"code": "002230", "name": "科大讯飞", "sector": "人工智能"},
    {"code": "600570", "name": "恒生电子", "sector": "金融科技"},
    {"code": "600703", "name": "三安光电", "sector": "LED/半导体"},
    {"code": "601919", "name": "中远海控", "sector": "航运"},
    {"code": "600089", "name": "特变电工", "sector": "电力设备"},
    {"code": "600150", "name": "中国船舶", "sector": "造船"},
    {"code": "600050", "name": "中国联通", "sector": "通信"},
]


class StockCodeDB:
    """股票代码数据库：内置 A股核心股票列表，支持模糊搜索。"""

    def __init__(self):
        # 去重
        seen = set()
        self._codes = []
        for item in CODE_LIST:
            if item["code"] not in seen:
                seen.add(item["code"])
                self._codes.append(item)

    def all_codes(self) -> List[dict]:
        return list(self._codes)

    def search(self, query: str, limit: int = 10) -> List[dict]:
        """
        模糊搜索股票代码 / 名称 / 板块。
        - 代码精确匹配优先
        - 其次是名称包含匹配
        - 其次是板块包含匹配
        - 最后是部分字符匹配
        """
        q = str(query or "").strip().lower()
        if not q:
            return []
        exact_code = [c for c in self._codes if c["code"] == q]
        if exact_code:
            return exact_code[:limit]
        name_hits = [c for c in self._codes if q in c["name"].lower()]
        sector_hits = [c for c in self._codes if q in c.get("sector", "").lower() and c not in name_hits]
        partial_hits = []
        for c in self._codes:
            if c in name_hits or c in sector_hits:
                continue
            if q in c["code"]:
                partial_hits.append(c)
        return (name_hits + sector_hits + partial_hits)[:limit]

    def get_name(self, code: str) -> Optional[str]:
        for c in self._codes:
            if c["code"] == code:
                return c["name"]
        return None

    def get_sector(self, code: str) -> Optional[str]:
        for c in self._codes:
            if c["code"] == code:
                return c.get("sector")
        return None
