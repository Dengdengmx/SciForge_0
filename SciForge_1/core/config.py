# core/config.py
import os
import json

class GlobalConfig:
    """全局配置单例引擎：管理软件中所有的标签、模板、字典项"""
    _file = os.path.join(os.getcwd(), "sciforge_global.json")
    _data = {}

    @classmethod
    def load(cls):
        if os.path.exists(cls._file):
            try:
                with open(cls._file, 'r', encoding='utf-8') as f:
                    cls._data = json.load(f)
            except:
                pass
        
        # 默认基础结构兜底
        if not cls._data:
            cls._data = {
                "archive_root": os.path.join(os.getcwd(), "SciForge_Archive"), 
                "archive_tags": ["🧬 课题: ProDesigner", "🧪 课题: SFTSV-Gc", "🔬 常规实验"],
                "sample_types": ["🧬 质粒", "🧪 蛋白", "🧫 细胞", "🦠 菌种", "💧 核酸", "📦 其他耗材"],
                "eln_templates": {}
            }

        # 【核心增强】：智能合并预设模板
        # 预设的强大生化实验模板库
        preset_templates = {
            "📦 寄快递": "【寄快递】\n物品内容：\n快递单号：\n收件方：\n",
            "📥 收快递": "【收快递】\n物品内容：\n存放位置：\n存储条件：\n",
            "🧬 分子构建": "【分子构建】\n目的基因：\n载体名称：\n酶切位点：\n预期大小：\n",
            "💧 质粒提取": "【质粒提取】\n菌株/质粒：\n浓度(ng/uL)：\nA260/280：\n",
            "🧪 蛋白纯化": "【蛋白纯化】\n目标蛋白：\n层析柱(Ni/SEC)：\n洗脱条件：\n预估浓度：\n",
            "🧫 挑单克隆": "【挑单克隆】\n平板抗性：\n挑选克隆数：\n培养条件：\n",
            "✉️ 送测序": "【送测序】\n测序公司：\n样本数量：\n使用引物：\n",
            "🦠 接种菌": "【接种菌】\n菌株/质粒：\n培养基(LB/TB)：\n抗生素：\n",
            "⚡ 转化": "【转化】\n感受态细胞：\n质粒/连接产物：\n涂布板抗性：\n",
            "🔬 细胞传代": "【细胞传代/铺板】\n细胞系：\n代数：\n接种密度：\n培养基：\n",
            "📊 ELISA": "【ELISA 检测】\n检测靶标：\n包被浓度：\n一抗稀释：\n二抗稀释：\n",
            "📝 组会汇报": "【组会/汇报】\n汇报主题：\n核心文献：\n需准备数据：\n",
            # ... （前面是你已有的模板代码）
            "🐁 小鼠解剖": "【小鼠解剖】\n品系/日龄：\n毛色/体重：\n提取器官：\n",
            
            # 自动化脚本专用的触发模板
            "📈 SPR 亲和力分析": "【SPR】\n实验目的：测定蛋白与配体的结合动力学\n配体(Ligand)：\n分析物(Analyte)：\n缓冲液(Buffer)：\n流速(μL/min)：\n",
            "📉 AKTA 蛋白纯化": "【AKTA】\n层析柱型号：\n样品名称：\n缓冲液A (平衡)：\n缓冲液B (洗脱)：\n洗脱梯度：\n",
            
            # ... （前面是你已有的模板代码）
            "🔥 BLI 表位聚类/热图": "【BLI 热图】\n实验目的：抗体表位竞争分析\n参考基准(Ref)：PBST\n样本数量：\n",
            
            # 【新增：序列分析模板】
            "🧬 核酸/蛋白 序列分析": "【序列分析】\n实验目的：序列核对与特征分析\n目标基因/蛋白：\n测序引物：\n分析结论：\n",
            # ... （前面是你已有的模板代码）
            "🖼️ 科研大图拼板组装": "【科研拼板】\n实验目的：组装多组结果图\n包含子图说明：\n",
            
            # 【新增：3D 结构解析模板】
            "🧊 蛋白质 3D 结构分析": "【3D 结构】\n目标蛋白：\nPDB ID / 来源：\n突变位点/核心表位：\n"
        }

        # 执行无损合并：只添加本地没有的模板，绝不删除用户自定义的模板
        if "eln_templates" not in cls._data:
            cls._data["eln_templates"] = {}
            
        needs_save = False
        for k, v in preset_templates.items():
            if k not in cls._data["eln_templates"]:
                cls._data["eln_templates"][k] = v
                needs_save = True
                
        # 确保 archive_root 节点存在
        if "archive_root" not in cls._data:
            cls._data["archive_root"] = os.path.join(os.getcwd(), "SciForge_Archive")
            needs_save = True

        if needs_save:
            cls.save()

    @classmethod
    def save(cls):
        try:
            with open(cls._file, 'w', encoding='utf-8') as f:
                json.dump(cls._data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[GlobalConfig] 保存失败: {e}")

    @classmethod
    def get(cls, key, default=None):
        return cls._data.get(key, default)

    @classmethod
    def set(cls, key, val):
        cls._data[key] = val
        cls.save()

# 模块导入时自动执行一次加载和无损合并
GlobalConfig.load()