# controllers/ctrl_sample_hub.py
import os
import json
import uuid

class SampleHubLogic:
    def __init__(self):
        self.config_file = os.path.join(os.getcwd(), "sciforge_physical_map.json")
        self.data_file = os.path.join(os.getcwd(), "sciforge_sample_items.json")
        self.equipments = {}
        self.aliases = {}
        self.items = {}
        self._load_data()

    def _load_data(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "equipments" in data:
                        self.equipments = data.get("equipments", {})
                        self.aliases = data.get("aliases", {})
                    else:
                        self.equipments = {k: v for k, v in data.items() if k != "aliases"}
                        self.aliases = data.get("aliases", {})
            except: self._init_default()
        else: self._init_default()
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.items = json.load(f)
            except: self.items = {}

    def save_data(self):
        data_to_save = {"equipments": self.equipments, "aliases": self.aliases}
        with open(self.config_file, 'w', encoding='utf-8') as f: json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        with open(self.data_file, 'w', encoding='utf-8') as f: json.dump(self.items, f, ensure_ascii=False, indent=4)

    def _init_default(self):
        # 🌟 加入了极其贴心的 desc 说明字段
        self.equipments = {
            "equip_drawer": {
                "name": "实验台复合空间 (抽屉/柜)", "layout": "Grid", "rows": 7, "cols": 2, 
                "desc": "常温存放区。主要用于存放日常离心管、枪头、常温试剂盒等实验耗材。",
                "containers": {
                    "cont_top": {"id": "cont_top", "name": "顶部双开门柜", "type": "freeform", "r": 0, "c": 0, "rs": 3, "cs": 2},
                    "drawer_l": {"id": "drawer_l", "name": "中间左侧抽屉", "type": "freeform", "r": 3, "c": 0, "rs": 1, "cs": 1},
                    "drawer_r": {"id": "drawer_r", "name": "中间右侧抽屉", "type": "freeform", "r": 3, "c": 1, "rs": 1, "cs": 1},
                    "cont_bot": {"id": "cont_bot", "name": "底部双开门柜", "type": "freeform", "r": 4, "c": 0, "rs": 3, "cs": 2}
                }, "inner_boxes": {}
            },
            
            "equip_fridge": {
                "name": "双温区冰箱 (4℃/-20℃)", "layout": "Grid", "rows": 5, "cols": 2, 
                "desc": "双温区存储。4℃常放抗体/缓冲液；-20℃常放酶类/引物等易降解试剂。",
                "row_zones": {
                    "0": {"name": "❄️ 4℃ 冷藏区 (上层)", "color": "#107C10"},
                    "2": {"name": "🧊 -20℃ 冷冻区 (下层)", "color": "#0078D7"}
                },
                "containers": {
                    "f_4_1": {"id": "f_4_1", "name": "4℃ 第一层横板", "type": "freeform", "r": 0, "c": 0, "rs": 1, "cs": 2},
                    "f_4_2": {"id": "f_4_2", "name": "4℃ 第二层横板", "type": "freeform", "r": 1, "c": 0, "rs": 1, "cs": 2},
                    "f_20_1": {"id": "f_20_1", "name": "-20℃ 第一层隔板", "type": "freeform", "r": 2, "c": 0, "rs": 1, "cs": 2},
                    "f_20_2": {"id": "f_20_2", "name": "-20℃ 第二层隔板", "type": "freeform", "r": 3, "c": 0, "rs": 1, "cs": 2},
                    "f_20_3": {"id": "f_20_3", "name": "-20℃ 底部大抽屉", "type": "freeform", "r": 4, "c": 0, "rs": 1, "cs": 2}
                }, "inner_boxes": {}
            },
            
            "equip_cabinet": {
                "name": "4℃ 层析柜 (左右双门)", "layout": "Grid", "rows": 5, "cols": 2, 
                "desc": "大体积冷藏区。主要用于存放层析柱、纯化填料、大瓶培养基等。",
                "containers": {
                    "c_l1": {"id": "c_l1", "name": "左侧第1层", "type": "freeform", "r": 0, "c": 0, "rs": 1, "cs": 1},
                    "c_r1": {"id": "c_r1", "name": "右侧第1层", "type": "freeform", "r": 0, "c": 1, "rs": 1, "cs": 1},
                    "c_l2": {"id": "c_l2", "name": "左侧第2层", "type": "freeform", "r": 1, "c": 0, "rs": 1, "cs": 1},
                    "c_r2": {"id": "c_r2", "name": "右侧第2层", "type": "freeform", "r": 1, "c": 1, "rs": 1, "cs": 1},
                }, "inner_boxes": {}
            },
            
            "equip_80": {
                "name": "-80℃ 超低温冰箱", "layout": "Grid", "rows": 5, "cols": 6, 
                "desc": "核心资产区。用于长期冻存甘油菌、质粒、细胞株、珍贵蛋白样本等。",
                "containers": {
                    "rack_1": {"id": "rack_1", "name": "1号冻存架", "type": "rack", "r": 0, "c": 0, "rs": 1, "cs": 1, "layers": 5, "boxes": 4}, 
                    "rack_2": {"id": "rack_2", "name": "2号冻存架", "type": "rack", "r": 0, "c": 1, "rs": 1, "cs": 1, "layers": 5, "boxes": 4},
                    "drawer_1": {"id": "drawer_1", "name": "底部巨型散装区", "type": "freeform", "r": 4, "c": 0, "rs": 1, "cs": 6}
                }, "inner_boxes": {}
            }
        }
        self.aliases = {}
        self.save_data()

    def get_aliases(self): return self.aliases
    def set_alias(self, path: str, new_name: str):
        if new_name.strip(): self.aliases[path] = new_name.strip()
        else: self.aliases.pop(path, None)
        self.save_data()

    def add_equipment(self, name, layout, config):
        eid = f"equip_{uuid.uuid4().hex[:6]}"; eq = {"name": name, "layout": layout, "containers": {}, "inner_boxes": {}}
        eq.update(config); self.equipments[eid] = eq; self.save_data(); return eid

    def resize_equipment_grid(self, equip_id, delta_row, delta_col):
        eq = self.equipments.get(equip_id)
        if not eq or eq.get("layout") != "Grid": return False, "只有网格布局的设备支持此伸缩操作！"
        new_rows = eq["rows"] + delta_row; new_cols = eq["cols"] + delta_col
        if new_rows < 1 or new_cols < 1: return False, "⚠️ 尺寸过小：至少保留 1x1 空间！"
        if delta_row < 0 or delta_col < 0:
            for cid, cont in eq["containers"].items():
                r, c, rs, cs = cont["r"], cont["c"], cont["rs"], cont["cs"]
                if r + rs > new_rows or c + cs > new_cols: return False, f"⚠️ 切割失败：边缘仍有容器【{cont['name']}】！"
        eq["rows"] = new_rows; eq["cols"] = new_cols; self.save_data(); return True, "改造成功！"

    def check_grid_space(self, equip_id, r, c, rs, cs, ignore_cid=None):
        eq = self.equipments.get(equip_id)
        if not eq or eq["layout"] != "Grid": return False, "非网格设备"
        if r < 0 or c < 0 or r + rs > eq["rows"] or c + cs > eq["cols"]: return False, "越界！"
        for cid, cont in eq["containers"].items():
            if cid == ignore_cid: continue
            cr, cc, crs, ccs = cont["r"], cont["c"], cont["rs"], cont["cs"]
            if not (c + cs <= cc or c >= cc + ccs or r + rs <= cr or r >= cr + crs): return False, "碰撞！"
        return True, "可用"

    def add_container(self, equip_id, container_info):
        eq = self.equipments.get(equip_id)
        if eq: cid = f"cont_{uuid.uuid4().hex[:6]}"; container_info["id"] = cid; eq["containers"][cid] = container_info; self.save_data(); return cid

    def delete_container(self, equip_id, cid):
        prefix = f"{equip_id}/{cid}"
        for path, items in self.items.items():
            if path.startswith(prefix) and items: return False, "⚠️ 极危拦截：内有样本！"
        eq = self.equipments.get(equip_id)
        if eq and cid in eq["containers"]: del eq["containers"][cid]; self.save_data(); return True, "拆除成功。"
        return False, "不存在。"

    def get_inner_boxes(self, equip_id, zone_path): return self.equipments.get(equip_id, {}).get("inner_boxes", {}).get(zone_path, {})
    def add_inner_box(self, equip_id, zone_path, box_info):
        eq = self.equipments.get(equip_id)
        if eq:
            if "inner_boxes" not in eq: eq["inner_boxes"] = {}
            if zone_path not in eq["inner_boxes"]: eq["inner_boxes"][zone_path] = {}
            bid = f"ibox_{uuid.uuid4().hex[:6]}"; box_info["id"] = bid; eq["inner_boxes"][zone_path][bid] = box_info; self.save_data(); return bid
    def delete_inner_box(self, equip_id, zone_path, box_id):
        prefix = f"{zone_path}/{box_id}"
        if prefix in self.items and self.items[prefix]: return False, "⚠️ 极危拦截：内有样本！"
        eq = self.equipments.get(equip_id)
        if eq and zone_path in eq.get("inner_boxes", {}) and box_id in eq["inner_boxes"][zone_path]:
            del eq["inner_boxes"][zone_path][box_id]; self.save_data(); return True, "移出成功。"
        return False, "未找到。"

    def get_location_data(self, path: str): return self.items.get(path, {})
    def update_item(self, path: str, item_id: str, item_info: dict):
        if path not in self.items: self.items[path] = {}
        self.items[path][item_id] = item_info; self.save_data()
    def add_freeform_item(self, path: str, item_info: dict):
        uid = f"item_{uuid.uuid4().hex[:8]}"; self.update_item(path, uid, item_info)
    def delete_item(self, path: str, item_id: str):
        if path in self.items and item_id in self.items[path]: del self.items[path][item_id]; self.save_data()
    def batch_add_items(self, path: str, well_ids: list, base_info: dict):
        if path not in self.items: self.items[path] = {}
        sorted_wells = sorted(well_ids, key=lambda w: (w[0], int(w[1:])))
        for i, well_id in enumerate(sorted_wells):
            import copy
            info = copy.deepcopy(base_info); info["name"] = f"{base_info['name']}-{i+1}"
            self.items[path][well_id] = info
        self.save_data()
    # ==========================================
    # 🧠 全局天眼与外部对接 API
    # ==========================================
    def get_full_alias_path(self, raw_path: str) -> str:
        """【路由解析器】将机器路径翻译为绝对物理路径"""
        parts = raw_path.split('/')
        aliased_parts = []
        acc = ""
        for p in parts:
            acc = f"{acc}/{p}" if acc else p
            if p in self.equipments:
                aliased_parts.append(self.aliases.get(acc, self.equipments[p]["name"]))
            elif len(parts) > 0 and parts[0] in self.equipments and p in self.equipments[parts[0]].get("containers", {}):
                aliased_parts.append(self.aliases.get(acc, self.equipments[parts[0]]["containers"][p]["name"]))
            elif len(parts) > 1 and parts[0] in self.equipments and p in self.equipments[parts[0]].get("inner_boxes", {}).get("/".join(parts[:-1]), {}):
                aliased_parts.append(self.aliases.get(acc, self.equipments[parts[0]]["inner_boxes"]["/".join(parts[:-1])][p]["name"]))
            else:
                if p not in ["top", "bottom", "left", "right"]:
                    aliased_parts.append(self.aliases.get(acc, p))
        return " > ".join(aliased_parts)

    def global_search(self, keyword: str) -> list:
        """🚀【天眼搜索 API】供外部模块调用"""
        results = []
        if not keyword or not str(keyword).strip(): return results
        kw = str(keyword).lower().strip()
        
        for path, wells in self.items.items():
            if not wells: continue
            
            human_readable_loc = self.get_full_alias_path(path)
            
            for well_id, info in wells.items():
                search_text = f"{info.get('name','')} {info.get('type','')} {info.get('owner','')} {info.get('notes','')} {well_id}".lower()
                
                if kw in search_text:
                    is_freeform = str(well_id).startswith("item_")
                    loc_display = f"{human_readable_loc} [散装]" if is_freeform else f"{human_readable_loc} [孔位: {well_id}]"
                    
                    results.append({
                        "uid": f"{path}::{well_id}",
                        "name": info.get("name", "未命名"),
                        "type": info.get("type", "未知"),
                        "location_str": loc_display,
                        "path": path,
                        "well_id": well_id,
                        "vol": info.get("vol", 0),
                        "unit": info.get("unit", "μL"),
                        "ft_count": info.get("ft", 0),
                        "owner": info.get("owner", ""),
                        "notes": info.get("notes", "")
                    })
        return sorted(results, key=lambda x: x["location_str"])