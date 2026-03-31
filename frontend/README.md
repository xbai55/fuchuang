# 反诈预警系统 - 前端

基于 React + TypeScript + Ant Design 的前端应用，采用 Coze 风格的深色主题。

## 🚀 启动指南

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

服务将在 `http://localhost:3000` 启动

### 3. 构建生产版本

```bash
npm run build
```

构建产物在 `dist/` 目录

## 📁 项目结构

```
frontend/
├── src/
│   ├── components/        # 组件
│   │   └── Sidebar.tsx   # 侧边栏
│   ├── pages/             # 页面
│   │   ├── Login.tsx      # 登录页
│   │   ├── Register.tsx   # 注册页
│   │   ├── ChatPage.tsx   # 聊天页面
│   │   ├── ContactsPage.tsx  # 联系人页面
│   │   └── Home.tsx       # 主页面
│   ├── services/          # API 服务
│   │   └── api.ts         # API 客户端
│   ├── utils/             # 工具函数
│   │   └── storage.ts     # 本地存储
│   ├── types/             # TypeScript 类型
│   │   └── index.ts
│   ├── App.tsx            # 应用根组件
│   ├── main.tsx           # 入口文件
│   └── index.css          # 全局样式
├── public/                # 静态资源
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

## 🎨 设计风格

### 颜色主题

```javascript
colors: {
  primary: '#6366f1',        // 主色调
  secondary: '#8b5cf6',      // 辅助色
  dark: '#1a1a2e',           // 深色背景
  darker: '#16162a',         // 更深的背景
  'dark-lighter': '#1e1e38', // 浅一点的深色
}
```

### 组件样式

- **按钮**: 渐变背景，圆角设计
- **输入框**: 深色背景，聚焦时边框高亮
- **卡片**: 深色背景，边框分隔
- **聊天消息**: 圆角气泡，用户消息右侧，机器人消息左侧

## 📱 页面说明

### 1. 登录页 (`/login`)
- 用户名/密码登录
- 记住 Token 到 localStorage
- 登录成功后跳转到主页

### 2. 注册页 (`/register`)
- 用户名、邮箱、密码注册
- 密码确认验证
- 注册成功后自动登录

### 3. 主页 (`/`)
- 包含侧边栏和内容区域
- 根据路由显示不同页面

### 4. 聊天页面
- 实时聊天界面
- 发送消息进行反诈检测
- 显示风险等级和警告信息
- 支持 Markdown 格式显示

### 5. 联系人页面
- 联系人列表展示
- 添加/编辑/删除联系人
- 设置监护人
- 显示联系人关系和手机号

## 🔌 API 集成

### API 服务 (`src/services/api.ts`)

```typescript
import { authAPI, contactsAPI, fraudAPI } from './services/api';

// 认证
authAPI.login(data);
authAPI.register(data);
authAPI.getCurrentUser();
authAPI.updateUser(user_role, guardian_name);

// 联系人
contactsAPI.getContacts();
contactsAPI.createContact(data);
contactsAPI.updateContact(id, data);
contactsAPI.deleteContact(id);

// 反诈检测
fraudAPI.detect(data);
fraudAPI.getHistory();
```

### 请求拦截器

- 自动添加 Authorization Header
- Token 过期时自动跳转登录页

### 响应拦截器

- 统一处理错误
- 401 状态码自动登出

## 🔒 本地存储

使用 `src/utils/storage.ts` 管理本地存储：

```typescript
import { storage } from './utils/storage';

// Token 操作
storage.getToken();
storage.setToken(token);
storage.removeToken();

// 用户信息操作
storage.getUser();
storage.setUser(user);
storage.removeUser();

// 检查登录状态
storage.isAuthenticated();
```

## 🧩 组件说明

### Sidebar（侧边栏）

功能：
- 导航菜单（对话预警、联系人设置）
- 用户信息展示
- 退出登录
- 个人信息设置

### 聊天界面

功能：
- 消息发送
- 实时风险检测
- 风险等级显示（低/中/高）
- Markdown 渲染
- 自动滚动到底部

### 联系人页面

功能：
- 联系人列表
- 添加联系人（模态框）
- 编辑联系人
- 删除联系人
- 设置监护人

## 🎯 TypeScript 类型

所有类型定义在 `src/types/index.ts`：

```typescript
// 用户
interface User {
  id: number;
  username: string;
  email: string;
  user_role: 'elderly' | 'student' | 'finance' | 'general';
  guardian_name: string;
}

// 联系人
interface Contact {
  id: number;
  name: string;
  phone: string;
  relationship: string;
  is_guardian: boolean;
  // ...
}

// 反诈检测
interface FraudDetectionResponse {
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high';
  scam_type: string;
  warning_message: string;
  final_report: string;
  guardian_alert: boolean;
}
```

## 🔧 配置

### 环境变量

创建 `.env` 文件：

```bash
VITE_API_URL=http://localhost:8000
```

### Tailwind CSS

配置文件：`tailwind.config.js`

自定义颜色和组件样式在 `index.css` 中。

### 路由配置

使用 React Router v6：

```typescript
<BrowserRouter>
  <Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/register" element={<Register />} />
    <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
  </Routes>
</BrowserRouter>
```

## 🧪 测试

### 本地测试

1. 启动后端服务
2. 启动前端服务
3. 访问 `http://localhost:3000`
4. 注册/登录账号
5. 测试聊天和联系人功能

### API 测试

打开浏览器开发者工具 → Network，查看请求和响应。

## 📝 开发建议

1. **代码风格**: 遵循 ESLint 和 Prettier 配置
2. **组件命名**: 使用 PascalCase
3. **文件命名**: 使用 kebab-case 或 PascalCase
4. **类型安全**: 充分利用 TypeScript 类型检查
5. **状态管理**: 使用 React Hooks

## 🚨 注意事项

1. 确保后端服务已启动
2. 检查 API 地址配置（`VITE_API_URL`）
3. Token 存储在 localStorage，生产环境建议使用更安全的方式
4. 图标使用 Ant Design Icons

## 📦 依赖说明

主要依赖：
- `react@^18.2.0` - React 框架
- `react-dom@^18.2.0` - React DOM
- `react-router-dom@^6.20.0` - 路由
- `antd@^5.12.0` - UI 组件库
- `axios@^1.6.2` - HTTP 客户端
- `react-markdown@^9.0.1` - Markdown 渲染
- `tailwindcss@^3.3.6` - CSS 框架

## 🎨 自定义主题

修改 `tailwind.config.js` 和 `index.css` 来自定义主题：

```javascript
// tailwind.config.js
export default {
  theme: {
    extend: {
      colors: {
        primary: '#your-color',
        // ...
      }
    }
  }
}
```

```css
/* index.css */
@layer components {
  .btn-primary {
    @apply bg-primary text-white px-6 py-2.5 rounded-lg;
    /* 自定义样式 */
  }
}
```

## 🔗 相关链接

- [React 文档](https://react.dev/)
- [Ant Design 文档](https://ant.design/)
- [Tailwind CSS 文档](https://tailwindcss.com/)
- [Vite 文档](https://vitejs.dev/)
