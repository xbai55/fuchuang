import { useState, useEffect } from 'react';
import { Layout, Button, Modal, Form, Input, Select, message, List, Popconfirm, Tag, Empty } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, PhoneOutlined } from '@ant-design/icons';
import { contactsAPI } from '../services/api';
import type { Contact, ContactCreate } from '../types';
import Sidebar from '../components/Sidebar';

const { Content } = Layout;

interface ContactsPageProps {
  onPageChange: (page: 'chat' | 'contacts') => void;
}

export default function ContactsPage({ onPageChange }: ContactsPageProps) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    loadContacts();
  }, []);

  const loadContacts = async () => {
    setLoading(true);
    try {
      const data = await contactsAPI.getContacts();
      setContacts(data);
    } catch (error) {
      message.error('加载联系人失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingContact(null);
    form.resetFields();
    setIsModalOpen(true);
  };

  const handleEdit = (contact: Contact) => {
    setEditingContact(contact);
    form.setFieldsValue(contact);
    setIsModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await contactsAPI.deleteContact(id);
      message.success('删除成功');
      loadContacts();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleSubmit = async (values: ContactCreate) => {
    try {
      if (editingContact) {
        await contactsAPI.updateContact(editingContact.id, values);
        message.success('更新成功');
      } else {
        await contactsAPI.createContact(values);
        message.success('添加成功');
      }
      setIsModalOpen(false);
      loadContacts();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const handleSetGuardian = async (contact: Contact) => {
    try {
      await contactsAPI.updateContact(contact.id, { is_guardian: true });
      message.success('已设为监护人');
      loadContacts();
    } catch (error) {
      message.error('设置失败');
    }
  };

  return (
    <Layout className="bg-darker min-h-screen">
      <Sidebar currentPage="contacts" onPageChange={onPageChange} />
      <Content className="ml-[260px] p-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-bold text-white">联系人设置</h1>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd} className="btn-primary">
              添加联系人
            </Button>
          </div>

          <div className="card-dark">
            {contacts.length === 0 ? (
              <Empty
                description={
                  <div>
                    <div className="text-gray-400 mb-2">暂无联系人</div>
                    <div className="text-sm text-gray-500">添加联系人后，高风险时系统会自动通知监护人</div>
                  </div>
                }
              />
            ) : (
              <List
                loading={loading}
                dataSource={contacts}
                renderItem={(contact) => (
                  <List.Item
                    actions={[
                      !contact.is_guardian && (
                        <Button
                          type="link"
                          onClick={() => handleSetGuardian(contact)}
                          className="text-primary hover:text-secondary"
                        >
                          设为监护人
                        </Button>
                      ),
                      <Button
                        type="link"
                        icon={<EditOutlined />}
                        onClick={() => handleEdit(contact)}
                      >
                        编辑
                      </Button>,
                      <Popconfirm
                        title="确定要删除这个联系人吗？"
                        onConfirm={() => handleDelete(contact.id)}
                        okText="确定"
                        cancelText="取消"
                      >
                        <Button type="link" danger icon={<DeleteOutlined />}>
                          删除
                        </Button>
                      </Popconfirm>,
                    ]}
                  >
                    <List.Item.Meta
                      avatar={
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white font-medium">
                          {contact.name.charAt(0).toUpperCase()}
                        </div>
                      }
                      title={
                        <div className="flex items-center gap-2">
                          <span className="text-white font-medium">{contact.name}</span>
                          {contact.is_guardian && (
                            <Tag color="red">监护人</Tag>
                          )}
                        </div>
                      }
                      description={
                        <div className="flex items-center gap-4 text-gray-400">
                          <span className="flex items-center gap-1">
                            <PhoneOutlined />
                            {contact.phone}
                          </span>
                          <span>{contact.relationship}</span>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </div>

          <div className="mt-6 p-4 card-dark">
            <h3 className="text-lg font-medium text-white mb-2">💡 提示</h3>
            <ul className="text-gray-400 text-sm space-y-1 list-disc list-inside">
              <li>设置监护人后，高风险时系统会自动通知</li>
              <li>建议添加家人、亲友等可信赖的联系人</li>
              <li>每位用户只能设置一个监护人</li>
            </ul>
          </div>
        </div>
      </Content>

      {/* 添加/编辑联系人模态框 */}
      <Modal
        title={editingContact ? '编辑联系人' : '添加联系人'}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setIsModalOpen(false)}>
            取消
          </Button>,
          <Button key="submit" type="primary" onClick={() => form.submit()}>
            {editingContact ? '保存' : '添加'}
          </Button>,
        ]}
      >
        <Form
          form={form}
          onFinish={handleSubmit}
          layout="vertical"
        >
          <Form.Item
            label="姓名"
            name="name"
            rules={[{ required: true, message: '请输入姓名' }]}
          >
            <Input placeholder="请输入姓名" />
          </Form.Item>

          <Form.Item
            label="手机号"
            name="phone"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1[3-9]\d{9}$/, message: '请输入有效的手机号' }
            ]}
          >
            <Input placeholder="请输入手机号" />
          </Form.Item>

          <Form.Item
            label="关系"
            name="relationship"
            rules={[{ required: true, message: '请选择关系' }]}
          >
            <Select placeholder="请选择关系">
              <Select.Option value="家人">家人</Select.Option>
              <Select.Option value="亲友">亲友</Select.Option>
              <Select.Option value="同事">同事</Select.Option>
              <Select.Option value="其他">其他</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="is_guardian"
            valuePropName="checked"
          >
            <div className="text-gray-400">
              设为监护人（高风险时自动通知）
            </div>
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}
