"""
Stock search service.
- A-shares: Sina suggest API (real-time, supports code/Chinese/pinyin)
- HK stocks: local major-stock list + matching
"""
import logging
import re
from typing import List

import requests
from pypinyin import lazy_pinyin, Style

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

_MARKET_MAP = {"11": "SH", "12": "SZ"}

# Major HK stocks (code, name)
_HK_STOCKS = [
    ("00700","腾讯控股"),("09988","阿里巴巴-W"),("03690","美团-W"),
    ("09999","网易-S"),("09618","京东集团-SW"),("01810","小米集团-W"),
    ("09888","百度集团-SW"),("00981","中芯国际"),("02318","中国平安"),
    ("00005","汇丰控股"),("00388","香港交易所"),("01299","友邦保险"),
    ("00939","建设银行"),("01398","工商银行"),("03988","中国银行"),
    ("00883","中国海洋石油"),("02020","安踏体育"),("01024","快手-W"),
    ("09961","携程集团-S"),("06618","京东健康"),("02015","理想汽车-W"),
    ("09868","小鹏汽车-W"),("02269","药明生物"),("01211","比亚迪股份"),
    ("00027","银河娱乐"),("01928","金沙中国"),("00002","中电控股"),
    ("00003","香港中华煤气"),("00006","电能实业"),("00011","恒生银行"),
    ("00012","恒基地产"),("00016","新鸿基地产"),("00017","新世界发展"),
    ("00023","东亚银行"),("00066","港铁公司"),("00175","吉利汽车"),
    ("00241","阿里健康"),("00267","中信股份"),("00288","万洲国际"),
    ("00386","中国石油化工"),("00669","创科实业"),("00688","中国海外发展"),
    ("00762","中国联通"),("00823","领展房产基金"),("00857","中国石油"),
    ("00902","华能国际电力"),("00914","海螺水泥"),("00916","龙源电力"),
    ("00960","龙湖集团"),("00968","信义光能"),("01038","长江基建集团"),
    ("01044","恒安国际"),("01093","石药集团"),("01109","华润置地"),
    ("01113","长实集团"),("01177","中国生物制药"),("01347","华虹半导体"),
    ("01378","中国宏桥"),("01876","百威亚太"),("01929","周大福"),
    ("01997","九龙仓置业"),("02007","碧桂园"),("02018","瑞声科技"),
    ("02282","美高梅中国"),("02313","申洲国际"),("02319","蒙牛乳业"),
    ("02382","舜宇光学科技"),("02388","中银香港"),("02628","中国人寿"),
    ("03323","中国建材"),("03692","翰森制药"),("03968","招商银行"),
    ("06098","碧桂园服务"),("06862","海底捞"),("09626","哔哩哔哩-W"),
    ("09901","新东方在线"),("09969","诺辉健康"),("01339","中国人民保险"),
    ("00101","恒隆地产"),("00142","第一太平"),("00267","中信股份"),
    ("00293","国泰航空"),("00316","东方海外国际"),("00322","康师傅控股"),
    ("00354","Chinasoft国际"),("00371","北控水务集团"),("00410","SOHO中国"),
    ("00489","东风集团股份"),("00522","ASMPT"),("00551","裕元集团"),
    ("00570","中国中药"),("00656","复星国际"),("00728","中国电信"),
    ("00753","中国国航"),("00772","阅文集团"),("00788","中国铁塔"),
    ("00813","世茂集团"),("00853","微创医疗"),("00868","信义玻璃"),
    ("00909","明源云"),("00966","中国太平"),("01024","快手-W"),
    ("01066","威高股份"),("01071","华电国际电力"),("01138","中远海能"),
    ("01171","兖矿能源"),("01193","华润燃气"),("01308","海丰国际"),
    ("01313","华润水泥"),("01316","耐世特汽车"),("01336","新华保险"),
    ("01347","华虹半导体"),("01359","中国信达"),("01368","特步国际"),
    ("01382","互太纺织"),("01458","周黑鸭"),("01548","金斯瑞生物"),
    ("01658","邮储银行"),("01772","赣锋锂业"),("01787","山东黄金"),
    ("01818","招金矿业"),("01898","中煤能源"),("01919","中远海控"),
    ("01951","锦欣生殖"),("01999","敏华控股"),("02013","微盟集团"),
    ("02018","瑞声科技"),("02020","安踏体育"),("02196","复星医药"),
    ("02238","广汽集团"),("02318","中国平安"),("02328","中国财险"),
    ("02331","李宁"),("02357","中航科工"),("02380","中国电力"),
    ("02601","中国太保"),("02607","上海医药"),("02611","国泰君安"),
    ("02618","京东物流"),("02628","中国人寿"),("02638","港灯-SS"),
    ("02669","中海物业"),("02688","新奥能源"),("02799","中国华融"),
    ("02899","紫金矿业"),("03311","中国建筑国际"),("03320","华润医药"),
    ("03331","维达国际"),("03360","远东宏信"),("03606","福耀玻璃"),
    ("03759","康龙化成"),("03799","达利食品"),("03888","金山软件"),
    ("03900","绿城中国"),("03908","中金公司"),("03958","东方证券"),
    ("03993","洛阳钼业"),("06030","中信证券"),("06060","众安在线"),
    ("06098","碧桂园服务"),("06160","百济神州"),("06185","康希诺生物"),
    ("06600","赛生药业"),("06616","环球新材国际"),("06690","海尔智家"),
    ("06699","时代天使"),("06806","申万宏源"),("06855","亚盛医药-B"),
    ("06969","思摩尔国际"),("09618","京东集团-SW"),("09626","哔哩哔哩-W"),
    ("09698","万国数据-SW"),("09868","小鹏汽车-W"),("09901","新东方在线"),
    ("09909","宝尊电商-SW"),("09922","九毛九"),("09923","移卡"),
    ("09926","康方生物-B"),("09961","携程集团-S"),("09969","诺辉健康"),
    ("09979","绿城管理控股"),("09983","建业新生活"),
    ("09987","百胜中国-SW"),("09988","阿里巴巴-W"),("09992","泡泡玛特"),
    ("09996","沛嘉医疗-B"),("09999","网易-S"),
]


class StockListService:
    """Search stocks via Sina suggest API (A-shares) + local HK list."""

    def search(self, query: str, limit: int = 20) -> List[dict]:
        if not query or not query.strip():
            return []
        q = query.strip()
        results = []

        # 1) A-share search via Sina suggest
        results.extend(self._search_sina(q, limit))

        # 2) HK search via local list
        results.extend(self._search_hk(q, limit))

        # Deduplicate and limit
        seen = set()
        deduped = []
        for r in results:
            key = f"{r['market']}_{r['symbol']}"
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped[:limit]

    def _search_sina(self, q: str, limit: int) -> List[dict]:
        try:
            url = f"https://suggest3.sinajs.cn/suggest/type=11,12,13&key={q}&name=suggestdata"
            resp = requests.get(url, headers=_HEADERS, timeout=5)
            resp.encoding = "gbk"
            text = resp.text
            if '"' not in text:
                return []
            raw = text.split('"')[1]
            if not raw:
                return []

            results = []
            for entry in raw.split(";"):
                fields = entry.split(",")
                if len(fields) < 5:
                    continue
                market = _MARKET_MAP.get(fields[1], "")
                if not market:
                    continue
                symbol = fields[2]
                name = fields[4]
                if symbol and name:
                    results.append({"symbol": symbol, "name": name, "market": market})
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            logger.error("Sina suggest failed: %s", e)
            return []

    def _search_hk(self, q: str, limit: int) -> List[dict]:
        """Search HK stocks from local list by code, name, or pinyin."""
        q_lower = q.lower()
        results = []
        for code, name in _HK_STOCKS:
            score = 0
            if code == q: score = 100
            elif code.startswith(q): score = 90
            elif q in code: score = 80
            elif name == q: score = 70
            elif q in name: score = 60
            else:
                # Pinyin match
                try:
                    clean = re.sub(r'[-—\sW]', '', name)
                    py_full = "".join(lazy_pinyin(clean))
                    py_init = "".join(lazy_pinyin(clean, style=Style.FIRST_LETTER))
                    if q_lower in py_full: score = 50 if py_full.startswith(q_lower) else 40
                    elif q_lower in py_init: score = 30 if py_init.startswith(q_lower) else 20
                except: pass
            if score > 0:
                results.append((score, {"symbol": code, "name": name, "market": "HK"}))

        results.sort(key=lambda x: -x[0])
        return [item for _, item in results[:limit]]


_service: StockListService = None

def get_stock_list_service() -> StockListService:
    global _service
    if _service is None:
        _service = StockListService()
    return _service
