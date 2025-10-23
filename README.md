# Sora2-Grsai
Sora2-Grsai 是一个 Grsai API 平台的 Sora2 模型视频生成工具，可用于批量重试同图片和提示词的视频生成，直至可过审的视频生成。适用于低概率过审的视频，用于减少操作次数，提升视频生成体验。不适用于完全不可能过审的视频生成。

API 供应商为 Grsai：https://grsai.com

# 前言
TMD OpenAI 这个鬼过审机制，就不能失败自动重试吗，搞的手动生成100份，平均只有20份成功，成功的20份里面只有1份不到能用，要点半天，妈的不点了，直接开始写工具。

# 使用说明
建议简单读一下开头的代码参数啥的看情况调整（然后有一部分不在标准库需要手动安装），但是不建议超过注释给出的建议值，然后自己部署直接跑，不要高频率请求轮询API，给API请求给人家搞成CC攻击了，毕竟大家都要用:(

# 演示截图
<img width="658" height="525" alt="image" src="https://github.com/user-attachments/assets/69b9b2f4-e10c-4605-bde1-d24af886e224" />
<img width="686" height="392" alt="image" src="https://github.com/user-attachments/assets/7b8dfdf1-0918-48ab-bbd1-948776b1d708" />
<img width="1038" height="714" alt="image" src="https://github.com/user-attachments/assets/92cd6175-00ce-4537-9f13-3edc9a3891c8" />
