# hubs_sample_hub.py
import re
import pandas as pd # 🚀 工业级数据处理引擎
from datetime import datetime
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtGui import QTextDocument

from view.ui_sample_hub import SampleHubUI, SampleItemDialog, ContainerSetupDialog, InnerBoxSetupDialog
from controllers.ctrl_sample_hub import SampleHubLogic

class SampleHubCoordinator:
    def __init__(self):
        self.ui = SampleHubUI()
        self.logic = SampleHubLogic()
        self.current_equip_id = ""
        self.current_drill_path = ""
        self._bind_signals()
        self.ui.refresh_home_view(self.logic.equipments, self.logic.get_aliases())

    def _bind_signals(self):
        self.ui.sig_equipment_clicked.connect(self.handle_equipment_clicked)
        self.ui.sig_drill_down.connect(self.handle_drill_down)
        self.ui.sig_alias_changed.connect(self.handle_alias_changed)
        self.ui.sig_add_container.connect(self.handle_add_container)
        self.ui.sig_delete_container.connect(self.handle_delete_container)
        self.ui.sig_add_inner_box.connect(self.handle_add_inner_box)
        self.ui.sig_delete_inner_box.connect(self.handle_delete_inner_box)
        self.ui.sig_resize_equipment.connect(self.handle_resize_equipment)
        
        # 💡 新增方向：设备与导表
        self.ui.sig_add_equipment.connect(self.handle_add_equipment)
        self.ui.sig_export_excel_requested.connect(self.handle_export_excel)
        self.ui.sig_import_excel_requested.connect(self.handle_import_excel)
        
        self.ui.sig_well_clicked.connect(self.handle_well_clicked)
        self.ui.sig_freeform_add.connect(self.handle_freeform_add)
        self.ui.sig_freeform_delete.connect(self.handle_freeform_delete)
        self.ui.sig_batch_add_requested.connect(self.handle_batch_add)
        self.ui.sig_batch_delete_requested.connect(self.handle_batch_delete)
        self.ui.sig_print_pdf_requested.connect(self.handle_print_pdf)
        self.ui.sig_paste_clipboard_requested.connect(self.handle_paste_clipboard)

    # ==========================================
    # 💡 方向三：上帝之手（实例化新设备）
    # ==========================================
    def handle_add_equipment(self, data):
        # 赋予新设备一个纯净的基础 Grid 模板
        self.logic.add_equipment(
            name=data["name"], 
            layout="Grid", 
            config={"rows": data["rows"], "cols": data["cols"], "desc": "自定义新建的物理设备。"}
        )
        self.ui.refresh_home_view(self.logic.equipments, self.logic.get_aliases())
        QMessageBox.information(self.ui, "新建成功", f"🎉 设备【{data['name']}】档案建立成功！\n\n您可以点击进入该设备，并通过底部的“+”按钮进一步扩建它的内部空间。")

    # ==========================================
    # 💡 方向二：工业级 Excel 高通量导表引擎
    # ==========================================
    def _get_wells_list(self, box_path):
        """根据路径推断孔位序列"""
        is_10x10 = "10x10" in box_path; is_12x8 = "12x8" in box_path; is_12x5 = "12x5" in box_path
        if is_10x10: rows = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]; cols = [str(i) for i in range(1, 11)]
        elif is_12x8: rows = ["A", "B", "C", "D", "E", "F", "G", "H"]; cols = [str(i) for i in range(1, 13)]
        elif is_12x5: rows = ["A", "B", "C", "D", "E"]; cols = [str(i) for i in range(1, 13)]
        else: rows = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]; cols = [str(i) for i in range(1, 10)]
        wells = []
        for r in rows:
            for c in cols: wells.append(f"{r}{c}")
        return wells

    def handle_export_excel(self, box_path):
        save_path, _ = QFileDialog.getSaveFileName(self.ui, "导出 Excel 模板", "SciForge_Box_Template.xlsx", "Excel Files (*.xlsx)")
        if not save_path: return
        
        try:
            box_data = self.logic.get_location_data(box_path)
            wells = self._get_wells_list(box_path)
            
            data_list = []
            for w in wells:
                info = box_data.get(w, {})
                data_list.append({
                    "孔位 (Well)": w,
                    "样本名称 (Name)": info.get("name", ""),
                    "样本类型 (Type)": info.get("type", ""),
                    "余量 (Vol)": info.get("vol", ""),
                    "单位 (Unit)": info.get("unit", ""),
                    "冻融次数 (F/T)": info.get("ft", ""),
                    "所有人 (Owner)": info.get("owner", ""),
                    "备注 (Notes)": info.get("notes", "")
                })
            
            df = pd.DataFrame(data_list)
            df.to_excel(save_path, index=False)
            QMessageBox.information(self.ui, "导出成功", f"🎉 Excel 模板导出成功！\n请填写后使用“导入”功能一键高通量录入。")
        except Exception as e:
            QMessageBox.warning(self.ui, "导出失败", f"发生了错误:\n{str(e)}\n\n请确保您已安装 pandas 和 openpyxl库。")

    def handle_import_excel(self, box_path):
        file_path, _ = QFileDialog.getOpenFileName(self.ui, "选择要导入的 Excel 文件", "", "Excel Files (*.xlsx *.xls)")
        if not file_path: return
        
        try:
            df = pd.read_excel(file_path)
            # 兼容性检查
            required_cols = ["孔位 (Well)", "样本名称 (Name)"]
            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"缺少必填列：{col}")
            
            valid_wells = set(self._get_wells_list(box_path))
            import_count = 0
            
            for index, row in df.iterrows():
                well = str(row["孔位 (Well)"]).strip()
                name = str(row["样本名称 (Name)"]).strip()
                
                # 如果没写名字，跳过或者当做删除
                if not name or name == 'nan':
                    self.logic.delete_item(box_path, well)
                    continue
                
                if well not in valid_wells: continue # 防呆：忽略错误的孔位号
                
                def safe_float(val, default=0.0):
                    try: return float(val) if pd.notna(val) else default
                    except: return default
                    
                def safe_int(val, default=0):
                    try: return int(val) if pd.notna(val) else default
                    except: return default

                info = {
                    "name": name,
                    "type": str(row.get("样本类型 (Type)", "🧬 质粒 (Plasmid)")) if pd.notna(row.get("样本类型 (Type)")) else "🧬 质粒 (Plasmid)",
                    "vol": safe_float(row.get("余量 (Vol)")),
                    "unit": str(row.get("单位 (Unit)", "μL")) if pd.notna(row.get("单位 (Unit)")) else "μL",
                    "ft": safe_int(row.get("冻融次数 (F/T)")),
                    "owner": str(row.get("所有人 (Owner)", "")) if pd.notna(row.get("所有人 (Owner)")) else "",
                    "notes": str(row.get("备注 (Notes)", "")) if pd.notna(row.get("备注 (Notes)")) else ""
                }
                self.logic.update_item(box_path, well, info)
                import_count += 1
                
            self.handle_drill_down(box_path, "9x9") # 瞬间原位刷新
            QMessageBox.information(self.ui, "导入成功", f"🚀 批量导入完成！共成功录入/更新了 {import_count} 个孔位的数据。")
            
        except Exception as e:
            QMessageBox.critical(self.ui, "导入失败", f"解析 Excel 失败，请检查模板格式！\n详细错误: {str(e)}")
        
        # 把它加在 handle_drill_down 附近
    def jump_to_specific_location(self, path: str, well_id: str):
        """💡 空间瞬移：被 DataHub 或主界面调用，自动展开 UI 直达样本"""
        try:
            parts = path.split('/')
            equip_id = parts[0]
            
            # 第一层：点开设备详情视图
            self.handle_equipment_clicked(equip_id)
            
            # 第二层：判断它属于哪种视图并强行 drill down 展开
            # 如果是散装区 (freeform)，直接展开到 freeform
            if "freeform" in self.logic.equipments[equip_id]["containers"].get(parts[1], {}).get("type", "freeform"):
                self.handle_drill_down(path, "freeform")
            # 如果里面包含了"层"和"盒"，说明它是 9x9 矩阵
            elif len(parts) > 2 and "盒" in parts[-1]:
                self.handle_drill_down(path, "9x9")
            # 其他管架形式，也展开到 9x9
            elif len(parts) > 1 and "12x" in self.logic.equipments[equip_id]["containers"].get(parts[1], {}).get("type", ""):
                self.handle_drill_down(path, "9x9")
                
            # (如果需要的话，还能在这里触发一个 闪烁动画 提示用户那个 well_id 在哪)
            print(f"✅ 瞬移成功！已为你自动打开路径：{path}，目标孔位：{well_id}")
        except Exception as e:
            print(f"瞬移失败：{e}")

    # ==========================================
    # 📋 剪贴板矩阵嗅探导入黑魔法
    # ==========================================
    def handle_paste_clipboard(self, box_path):
        from PyQt5.QtWidgets import QApplication
        text = QApplication.clipboard().text().strip()
        if not text:
            QMessageBox.warning(self.ui, "剪贴板为空", "未能从剪贴板检测到文本！请先在 Excel 中复制区域。")
            return
            
        # 1. 嗅探剪贴板文本并还原矩阵
        lines = text.split('\n')
        matrix = [line.split('\t') for line in lines]
        
        # 2. 匹配当前物理孔位
        is_10x10 = "10x10" in box_path; is_12x8 = "12x8" in box_path; is_12x5 = "12x5" in box_path
        if is_10x10: rows = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]; cols = [str(i) for i in range(1, 11)]
        elif is_12x8: rows = ["A", "B", "C", "D", "E", "F", "G", "H"]; cols = [str(i) for i in range(1, 13)]
        elif is_12x5: rows = ["A", "B", "C", "D", "E"]; cols = [str(i) for i in range(1, 13)]
        else: rows = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]; cols = [str(i) for i in range(1, 10)]
            
        pending_data = {}
        for r_idx, row_items in enumerate(matrix):
            if r_idx >= len(rows): break
            r_char = rows[r_idx]
            for c_idx, val in enumerate(row_items):
                if c_idx >= len(cols): break
                val = val.strip()
                if val:  # 只有该格子里有字，才认为是有效样本
                    c_char = cols[c_idx]
                    well_id = f"{r_char}{c_char}"
                    pending_data[well_id] = val

        if not pending_data:
            QMessageBox.warning(self.ui, "未检测到有效数据", "剪贴板文本格式不正确或为空。请直接在 Excel 里框选连续的单元格复制。")
            return
            
        # 3. 弹窗让用户统一确认这批数据的共有属性
        dlg = SampleItemDialog(well_id=f"剪贴板矩阵({len(pending_data)}个)", parent=self.ui)
        dlg.input_notes.setPlaceholderText("这里的信息将统一应用到所有粘贴的样本上。名称将被剪贴板里的名字覆盖！")
        dlg.input_name.setText("自动嗅探名称覆盖")
        dlg.input_name.setEnabled(False) # 名称是固定的，不需要手改
        
        if dlg.exec_() and not dlg.is_delete:
            base_data = dlg.get_data()
            for well_id, cell_name in pending_data.items():
                # 深度拷贝，防止引用污染
                import copy
                specific_data = copy.deepcopy(base_data)
                specific_data["name"] = cell_name  # 用 Excel 里的真实名字覆盖
                self.logic.update_item(box_path, well_id, specific_data)
                
            self.handle_drill_down(box_path, "9x9")
            QMessageBox.information(self.ui, "神级导入成功", f"🚀 剪贴板矩阵解析完成！成功点亮 {len(pending_data)} 个孔位！")

    # ==========================================
    # 其他原有调度逻辑保持原样...
    # ==========================================
    def handle_resize_equipment(self, equip_id, delta_row, delta_col):
        success, msg = self.logic.resize_equipment_grid(equip_id, delta_row, delta_col)
        if not success: QMessageBox.warning(self.ui, "⚠️ 尺寸调整被拦截", msg)
        else: self.handle_equipment_clicked(equip_id)

    def handle_add_container(self, equip_id, r, c):
        dlg = ContainerSetupDialog(self.ui)
        if dlg.exec_():
            data = dlg.get_data(); is_safe, msg = self.logic.check_grid_space(equip_id, r, c, data["rs"], data["cs"])
            if not is_safe: QMessageBox.warning(self.ui, "空间不足", msg); return
            data["r"] = r; data["c"] = c; self.logic.add_container(equip_id, data); self.handle_equipment_clicked(equip_id)

    def handle_delete_container(self, equip_id, cid):
        if QMessageBox.question(self.ui, "确认", "确定拆除该容器？如果内有样本将被拦截。", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            is_deleted, msg = self.logic.delete_container(equip_id, cid)
            if not is_deleted: QMessageBox.critical(self.ui, "拦截", msg)
            else: self.handle_equipment_clicked(equip_id)

    def handle_add_inner_box(self, zone_path):
        dlg = InnerBoxSetupDialog(self.ui)
        if dlg.exec_():
            self.logic.add_inner_box(zone_path.split('/')[0], zone_path, dlg.get_data()); self.handle_drill_down(zone_path, "freeform")

    def handle_delete_inner_box(self, zone_path, box_id):
        if QMessageBox.question(self.ui, "确认", "确定移出？", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            is_del, msg = self.logic.delete_inner_box(zone_path.split('/')[0], zone_path, box_id)
            if not is_del: QMessageBox.critical(self.ui, "拦截", msg)
            else: self.handle_drill_down(zone_path, "freeform")

    def handle_equipment_clicked(self, equip_id):
        self.current_equip_id = equip_id; eq_data = self.logic.equipments.get(equip_id, {})
        if not eq_data: return
        self.ui.render_detail_view(equip_id, eq_data, self.logic.get_aliases())

    def handle_drill_down(self, path, view_type):
        self.current_drill_path = path; aliases = self.logic.get_aliases()
        if view_type == "boxes": self.ui.render_layer_boxes_view(path, aliases)
        elif view_type == "9x9": self.ui.render_grid_9x9_view(path, self.logic.get_location_data(path), aliases)
        elif view_type == "freeform": self.ui.render_freeform_view(path, self.logic.get_location_data(path), self.logic.get_inner_boxes(path.split('/')[0], path), aliases)

    def handle_alias_changed(self, path, new_name):
        self.logic.set_alias(path, new_name); curr = self.ui.stack.currentIndex()
        if curr == 0: self.ui.refresh_home_view(self.logic.equipments, self.logic.get_aliases())
        elif curr == 1: self.handle_equipment_clicked(self.current_equip_id)
        elif curr == 3: self.handle_drill_down(self.current_drill_path, "boxes")
        elif curr == 2: self.handle_drill_down(self.current_drill_path, "9x9")
        elif curr == 4: self.handle_drill_down(self.current_drill_path, "freeform")

    def handle_well_clicked(self, box_path, well_id):
        dlg = SampleItemDialog(well_id, self.logic.get_location_data(box_path).get(well_id), self.ui)
        if dlg.exec_():
            if dlg.is_delete: self.logic.delete_item(box_path, well_id)
            elif dlg.get_data()["name"]: self.logic.update_item(box_path, well_id, dlg.get_data())
            self.handle_drill_down(box_path, "9x9")
    def handle_batch_add(self, box_path, selected_wells):
        if not selected_wells: return
        dlg = SampleItemDialog(well_id=f"批量({len(selected_wells)}孔)", parent=self.ui)
        if dlg.exec_() and not dlg.is_delete and dlg.get_data()["name"]:
            self.logic.batch_add_items(box_path, selected_wells, dlg.get_data()); self.handle_drill_down(box_path, "9x9")
    def handle_batch_delete(self, box_path, selected_wells):
        if not selected_wells: return
        if QMessageBox.question(self.ui, "清空", f"确定清空 {len(selected_wells)} 孔？", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            for wid in selected_wells: self.logic.delete_item(box_path, wid)
            self.handle_drill_down(box_path, "9x9")
    def handle_freeform_add(self, list_path):
        dlg = SampleItemDialog(parent=self.ui)
        if dlg.exec_() and not dlg.is_delete and dlg.get_data()["name"]:
            self.logic.add_freeform_item(list_path, dlg.get_data()); self.handle_drill_down(list_path, "freeform")
    def handle_freeform_delete(self, list_path, item_id):
        self.logic.delete_item(list_path, item_id); self.handle_drill_down(list_path, "freeform")

    def handle_print_pdf(self):
        items_data = self.logic.items
        if not items_data or all(not items for items in items_data.values()): return QMessageBox.warning(self.ui, "提示", "库存为空！")
        save_path, _ = QFileDialog.getSaveFileName(self.ui, "导出清单", "SciForge_Inventory.pdf", "PDF (*.pdf)")
        if not save_path: return
        aliases = self.logic.get_aliases()
        def get_full_alias_path(raw_path):
            parts = raw_path.split('/'); aliased_parts = []; acc = ""
            for p in parts:
                acc = f"{acc}/{p}" if acc else p
                if p in self.logic.equipments: aliased_parts.append(aliases.get(acc, self.logic.equipments[p]["name"]))
                elif len(parts)>0 and parts[0] in self.logic.equipments and p in self.logic.equipments[parts[0]].get("containers", {}):
                    aliased_parts.append(aliases.get(acc, self.logic.equipments[parts[0]]["containers"][p]["name"]))
                else:
                    if p not in ["top", "bottom", "left", "right"]: aliased_parts.append(aliases.get(acc, p))
            return " > ".join(aliased_parts)

        html = f"<html><head><meta charset='utf-8'><style>body {{font-family: 'SimHei'; font-size: 10pt;}} h2 {{text-align: center; color: #0078D7;}} table {{border-collapse: collapse; width:100%;}} th, td {{border: 1px solid #aaa; padding: 6px;}} th {{background-color: #0078D7; color: white;}}</style></head><body><h2>SciForge 物理映射版清单</h2><table border='1'><tr><th>样本基名</th><th>类型</th><th>所有人</th><th>📍 物理位置</th><th>备注</th></tr>"
        for path in sorted(items_data.keys()):
            if not items_data[path]: continue
            grouped = {}
            for wid, info in items_data[path].items():
                gk = (re.sub(r'-\d+$', '', info.get("name", "")).strip(), info.get("type", ""), info.get("owner", ""), info.get("notes", ""), str(wid).startswith("item_"))
                grouped.setdefault(gk, []).append(wid)
            for (bn, ty, ow, no, is_free), wlist in grouped.items():
                loc = f"<b>{get_full_alias_path(path)}</b><br><span style='color:#888;'>[散装 - {len(wlist)}份]</span>" if is_free else f"<b>{get_full_alias_path(path)}</b><br><span style='color:#D83B01;'>[{wlist[0]} ... {wlist[-1]}]</span> ({len(wlist)}管)"
                html += f"<tr><td><b>{bn}</b></td><td>{ty}</td><td>{ow}</td><td>{loc}</td><td>{no}</td></tr>"
        html += "</table></body></html>"
        try:
            printer = QPrinter(); printer.setOutputFormat(QPrinter.PdfFormat); printer.setOutputFileName(save_path)
            doc = QTextDocument(); doc.setHtml(html); doc.print_(printer); QMessageBox.information(self.ui, "成功", f"导出至:\n{save_path}")
        except Exception as e: QMessageBox.warning(self.ui, "失败", str(e))