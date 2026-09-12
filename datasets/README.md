# datasets/ 真实数据来源与许可

本目录存放真实公开数据集。`raw/` 下的大体积原始文件不入库
（`.gitignore` 已排除，可按下方来源重新下载）；小体积的处理后文件
随仓库提交，保证离线可复现。

## Online Retail（→ 案例 22）

- 来源：UCI Machine Learning Repository，数据集 ID 352，许可 CC BY 4.0
- 引用：Chen, Sain, Guo (2012). *Online retail: a data mining approach to
  predict the popularity of online retailing*
- 规模：541,909 笔真实交易（英国电商，2010-12-01 ~ 2011-12-09）
- 处理：`cases/22-replenishment-ads/data_real.py` —— 剔除取消单与价格长尾、
  取交易量 Top 200 SKU、对齐最后 240 天日历，生成 `retail_daily.csv`
  （随仓库提交，133 KB）

## Amazon-Google（→ 案例 08）

- 来源：Magellan / DeepMatcher 实体匹配基准
  （https://github.com/anhaidgroup/deepmatcher ，研究用途）
- 规模：Amazon 1,363 商品 × Google 3,226 商品，人工标注对
  train 6,874（正 699）/ test 2,293（正 234）
- 文件：`amazon_google/*.csv`（随仓库提交，440 KB）
- 处理：`cases/08-material-search/er_real.py` 直接消费原始表与标注

## 尝试过但未接入的源（网络/可得性原因，如实记录）

- CMRC 2018（中文阅读理解，拟用于案例 01）：hf-mirror 文件路径 404，未接入
- ESICUP 3D 装箱实例（拟用于案例 06）：官方站点结构不稳定，未接入
- Abt-Buy（拟用于案例 08 备选）：原托管地址 404，已用 Amazon-Google 替代
