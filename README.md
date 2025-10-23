# Sora2-Grsai
Sora2-Grsai 是一个 Grsai API 平台的 Sora2 模型视频生成工具，可用于批量重试同图片和提示词的视频生成，直至可过审的视频生成。适用于低概率过审的视频，用于减少操作次数，提升视频生成体验。不适用于完全不可能过审的视频生成。

API 供应商为 Grsai：https://grsai.com

# 前言
TMD OpenAI 这个鬼过审机制，就不能失败自动重试吗，搞的手动生成100份，平均只有20份成功，成功的20份里面只有1份不到能用，要点半天，妈的不点了，直接开始写工具。

# 使用说明
建议简单读一下开头的代码参数啥的看情况调整（然后有一部分不在标准库需要手动安装），但是不建议超过注释给出的建议值，然后自己部署直接跑，不要高频率请求轮询API，给API请求给人家搞成CC攻击了，毕竟大家都要用:(

1. 安装你的 Python：尚未测试可用版本范围，但是不建议低于 Python 3.8
2. 阅读源代码的 `import` 部分，并安装相关的依赖和库，我们尽可能的使用了常用库和标准库，应该非常好安装。
3. 如果你在 Windows系统 使用该程序，将程序放入单独的文件夹后，双击 `start.bat` 应该就可以直接跑了，Linux 系统 尚未进行测试。
4. 上传的图片必须要为链接，你可以自己找图床上传，或者在网上直接抓取对应的图片链接，或者自己部署公网下的服务器。
5. 如果你一个图片和提示词累计尝试了超过 20 遍都没有成功过一次，建议更换图片或提示词，一般20次都没有一个过的，基本上宣告这个不可能过审了，请不要浪费资源。

# 演示截图
<img width="1040" height="641" alt="image" src="https://github.com/user-attachments/assets/9410470f-90dc-4702-a9fb-a76bed8a0a56" />

<img width="686" height="392" alt="image" src="https://github.com/user-attachments/assets/7b8dfdf1-0918-48ab-bbd1-948776b1d708" />
<img width="1038" height="714" alt="image" src="https://github.com/user-attachments/assets/92cd6175-00ce-4537-9f13-3edc9a3891c8" />
