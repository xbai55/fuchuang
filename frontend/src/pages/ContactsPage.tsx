import { useEffect, useState } from 'react';
import { App, Button, Checkbox, Col, Empty, Form, Input, List, Modal, Popconfirm, Row, Select, Tag } from 'antd';
import { DeleteOutlined, EditOutlined, PhoneOutlined, PlusOutlined } from '@ant-design/icons';
import { contactsAPI } from '../services/api';
import { useI18n } from '../i18n';
import { maskPhone, maskUsername, USER_SETTINGS_CHANGED_EVENT } from '../utils/privacy';
import { storage } from '../utils/storage';
import type { Contact, ContactCreate } from '../types';

interface ContactsPageProps {
  onPageChange: (page: 'chat' | 'contacts') => void;
}

type ContactFormValues = ContactCreate;

type ApiError = {
  response?: {
    data?: {
      detail?: string;
      message?: string;
    };
  };
};

export default function ContactsPage({ onPageChange: _onPageChange }: ContactsPageProps) {
  const { message } = App.useApp();
  const { isZh } = useI18n();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [privacyMode, setPrivacyMode] = useState<boolean>(() => storage.getUser()?.privacy_mode ?? false);
  const [form] = Form.useForm<ContactFormValues>();

  const t = (zh: string, en: string) => (isZh ? zh : en);

  const relationshipLabels: Record<string, string> = {
    family: t('家人', 'Family'),
    friend: t('朋友', 'Friend'),
    coworker: t('同事', 'Coworker'),
    other: t('其他', 'Other'),
  };

  const relationshipTagColors: Record<string, string> = {
    family: 'gold',
    friend: 'blue',
    coworker: 'purple',
    other: 'default',
  };

  const loadContacts = async () => {
    setLoading(true);
    try {
      const data = await contactsAPI.getContacts();
      setContacts(data);
    } catch (error) {
      const apiError = error as ApiError;
      const errorMsg =
        apiError.response?.data?.detail ?? apiError.response?.data?.message ?? t('加载联系人失败', 'Failed to load contacts');
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadContacts();
  }, []);

  useEffect(() => {
    const syncPrivacy = () => {
      setPrivacyMode(storage.getUser()?.privacy_mode ?? false);
    };

    window.addEventListener('storage', syncPrivacy);
    window.addEventListener(USER_SETTINGS_CHANGED_EVENT, syncPrivacy);

    return () => {
      window.removeEventListener('storage', syncPrivacy);
      window.removeEventListener(USER_SETTINGS_CHANGED_EVENT, syncPrivacy);
    };
  }, []);

  const openCreateModal = () => {
    setEditingContact(null);
    form.setFieldsValue({
      name: '',
      phone: '',
      relationship: 'family',
      is_guardian: false,
    });
    setIsModalOpen(true);
  };

  const openEditModal = (contact: Contact) => {
    setEditingContact(contact);
    form.setFieldsValue({
      name: contact.name,
      phone: contact.phone,
      relationship: contact.relationship,
      is_guardian: contact.is_guardian,
    });
    setIsModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await contactsAPI.deleteContact(id);
      message.success(t('联系人已删除', 'Contact deleted'));
      await loadContacts();
    } catch (error) {
      const apiError = error as ApiError;
      const errorMsg =
        apiError.response?.data?.detail ?? apiError.response?.data?.message ?? t('删除联系人失败', 'Failed to delete contact');
      message.error(errorMsg);
    }
  };

  const handleSubmit = async (values: ContactFormValues) => {
    try {
      if (editingContact) {
        await contactsAPI.updateContact(editingContact.id, values);
        message.success(t('联系人已更新', 'Contact updated'));
      } else {
        await contactsAPI.createContact(values);
        message.success(t('联系人已创建', 'Contact created'));
      }
      setIsModalOpen(false);
      await loadContacts();
    } catch (error) {
      const apiError = error as ApiError;
      const errorMsg =
        apiError.response?.data?.detail ?? apiError.response?.data?.message ?? t('保存联系人失败', 'Failed to save contact');
      message.error(errorMsg);
    }
  };

  const handleSetGuardian = async (contact: Contact) => {
    try {
      await contactsAPI.updateContact(contact.id, { is_guardian: true });
      message.success(t('监护联系人已更新', 'Guardian contact updated'));
      await loadContacts();
    } catch (error) {
      const apiError = error as ApiError;
      const errorMsg =
        apiError.response?.data?.detail ?? apiError.response?.data?.message ?? t('更新监护联系人失败', 'Failed to update guardian contact');
      message.error(errorMsg);
    }
  };

  return (
    <div className="min-h-screen bg-darker ml-[260px] p-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">{t('紧急联系人', 'Emergency Contacts')}</h1>
            <p className="mt-1 text-sm text-gray-400">
              {t('为高风险预警预先配置可信联系人。', 'Configure trusted contacts for high-risk alerts.')}
            </p>
          </div>

          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal} className="btn-primary">
            {t('添加联系人', 'Add Contact')}
          </Button>
        </div>

        <div className="card-dark p-4">
          {contacts.length === 0 ? (
            <Empty description={<span className="text-gray-400">{t('暂无联系人', 'No contacts yet')}</span>} />
          ) : (
            <List
              loading={loading}
              dataSource={contacts}
              renderItem={(contact) => (
                <List.Item className="!py-4">
                  <div className="flex w-full flex-wrap items-start gap-3 sm:flex-nowrap sm:items-center sm:justify-between">
                    <List.Item.Meta
                      className="mb-0 min-w-[260px] flex-1"
                      avatar={
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-primary to-secondary text-white font-semibold">
                          {contact.name.charAt(0).toUpperCase()}
                        </div>
                      }
                      title={
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-white font-medium">{privacyMode ? maskUsername(contact.name) : contact.name}</span>
                          <Tag color={relationshipTagColors[contact.relationship] ?? 'default'} className="m-0 rounded-full">
                            {relationshipLabels[contact.relationship] ?? contact.relationship}
                          </Tag>
                          {contact.is_guardian ? (
                            <Tag color="red" className="m-0 rounded-full">
                              {t('监护人', 'Guardian')}
                            </Tag>
                          ) : (
                            <Button
                              size="small"
                              onClick={() => void handleSetGuardian(contact)}
                              className="!h-6 rounded-full border-amber-400/70 bg-amber-500/10 !px-2 text-[12px] !text-amber-200 hover:!border-amber-300 hover:!text-amber-100"
                            >
                              {t('设为监护人', 'Set as Guardian')}
                            </Button>
                          )}
                        </div>
                      }
                      description={
                        <div className="flex items-center gap-4 text-gray-400">
                          <span className="flex items-center gap-1">
                            <PhoneOutlined />
                            {privacyMode ? maskPhone(contact.phone) : contact.phone}
                          </span>
                        </div>
                      }
                    />

                    <div className="flex w-full items-center justify-start gap-2 sm:w-auto sm:justify-end">
                      <Button
                        type="default"
                        icon={<EditOutlined />}
                        onClick={() => openEditModal(contact)}
                        className="!h-8 rounded-full !px-3"
                      >
                        {t('编辑', 'Edit')}
                      </Button>

                      <Popconfirm
                        title={t('确认删除该联系人吗？', 'Delete this contact?')}
                        okText={t('删除', 'Delete')}
                        cancelText={t('取消', 'Cancel')}
                        onConfirm={() => void handleDelete(contact.id)}
                      >
                        <Button type="default" danger icon={<DeleteOutlined />} className="!h-8 rounded-full !px-3">
                          {t('删除', 'Delete')}
                        </Button>
                      </Popconfirm>
                    </div>
                  </div>
                </List.Item>
              )}
            />
          )}
        </div>
      </div>

      <Modal
        title={editingContact ? t('编辑联系人', 'Edit Contact') : t('添加联系人', 'Add Contact')}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onOk={() => form.submit()}
        okText={editingContact ? t('保存', 'Save') : t('创建', 'Create')}
        cancelText={t('取消', 'Cancel')}
      >
        <Form<ContactFormValues> form={form} layout="vertical" onFinish={(values) => void handleSubmit(values)}>
          <Row gutter={16}>
            <Col xs={24} sm={12}>
              <Form.Item
                label={t('姓名', 'Name')}
                name="name"
                rules={[{ required: true, message: t('请输入联系人姓名', 'Please enter contact name') }]}
              >
                <Input placeholder={t('姓名', 'Name')} />
              </Form.Item>
            </Col>

            <Col xs={24} sm={12}>
              <Form.Item
                label={t('关系', 'Relationship')}
                name="relationship"
                rules={[{ required: true, message: t('请选择关系', 'Please select relationship') }]}
              >
                <Select
                  options={[
                    { value: 'family', label: t('家人', 'Family') },
                    { value: 'friend', label: t('朋友', 'Friend') },
                    { value: 'coworker', label: t('同事', 'Coworker') },
                    { value: 'other', label: t('其他', 'Other') },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label={t('手机号', 'Phone Number')}
            name="phone"
            rules={[
              { required: true, message: t('请输入手机号', 'Please enter phone number') },
              { pattern: /^1[3-9]\d{9}$/, message: t('请输入有效的中国大陆手机号', 'Please enter a valid mainland China phone number') },
            ]}
          >
            <Input placeholder="13800000000" />
          </Form.Item>

          <Form.Item name="is_guardian" valuePropName="checked">
            <Checkbox>{t('将该联系人设为监护人', 'Set this contact as guardian')}</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
