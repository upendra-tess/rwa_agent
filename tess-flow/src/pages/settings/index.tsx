import { User, Shield, Bell, Palette, CreditCard } from "lucide-react";
import PageShell from "../../shared/PageShell";

const SettingsPage = () => {
  return (
    <PageShell>
      <div className="tf-settings-layout">
        {/* Profile */}
        <section className="tf-settings-section">
          <div className="tf-settings-section-header">
            <User size={16} strokeWidth={2} />
            <h3 className="tf-settings-section-title">Profile</h3>
          </div>
          <div className="tf-settings-section-body">
            <div className="tf-settings-field">
              <label className="tf-settings-label">Display Name</label>
              <input type="text" className="tf-settings-input" defaultValue="User" />
            </div>
            <div className="tf-settings-field">
              <label className="tf-settings-label">Email</label>
              <input type="email" className="tf-settings-input" defaultValue="user@example.com" />
            </div>
            <button type="button" className="tf-btn primary">Save Changes</button>
          </div>
        </section>

        {/* Security */}
        <section className="tf-settings-section">
          <div className="tf-settings-section-header">
            <Shield size={16} strokeWidth={2} />
            <h3 className="tf-settings-section-title">Security</h3>
          </div>
          <div className="tf-settings-section-body">
            <div className="tf-settings-item">
              <div className="tf-settings-item-info">
                <div className="tf-settings-item-label">Two-Factor Authentication</div>
                <div className="tf-settings-item-desc">Add an extra layer of security to your account</div>
              </div>
              <button type="button" className="tf-btn secondary">Enable</button>
            </div>
            <div className="tf-settings-item">
              <div className="tf-settings-item-info">
                <div className="tf-settings-item-label">Password</div>
                <div className="tf-settings-item-desc">Last changed 45 days ago</div>
              </div>
              <button type="button" className="tf-btn ghost">Change</button>
            </div>
          </div>
        </section>

        {/* Notifications */}
        <section className="tf-settings-section">
          <div className="tf-settings-section-header">
            <Bell size={16} strokeWidth={2} />
            <h3 className="tf-settings-section-title">Notifications</h3>
          </div>
          <div className="tf-settings-section-body">
            <div className="tf-settings-item">
              <div className="tf-settings-item-info">
                <div className="tf-settings-item-label">Task Completions</div>
                <div className="tf-settings-item-desc">Get notified when tasks finish</div>
              </div>
              <input type="checkbox" className="tf-settings-toggle" defaultChecked />
            </div>
            <div className="tf-settings-item">
              <div className="tf-settings-item-info">
                <div className="tf-settings-item-label">Approval Requests</div>
                <div className="tf-settings-item-desc">Get notified when agents need approval</div>
              </div>
              <input type="checkbox" className="tf-settings-toggle" defaultChecked />
            </div>
            <div className="tf-settings-item">
              <div className="tf-settings-item-info">
                <div className="tf-settings-item-label">Integration Alerts</div>
                <div className="tf-settings-item-desc">Get notified about connection issues</div>
              </div>
              <input type="checkbox" className="tf-settings-toggle" defaultChecked />
            </div>
          </div>
        </section>

        {/* Appearance */}
        <section className="tf-settings-section">
          <div className="tf-settings-section-header">
            <Palette size={16} strokeWidth={2} />
            <h3 className="tf-settings-section-title">Appearance</h3>
          </div>
          <div className="tf-settings-section-body">
            <div className="tf-settings-field">
              <label className="tf-settings-label">Theme</label>
              <select className="tf-settings-select">
                <option value="dark">Dark</option>
                <option value="light">Light</option>
                <option value="auto">Auto</option>
              </select>
            </div>
          </div>
        </section>

        {/* Billing */}
        <section className="tf-settings-section">
          <div className="tf-settings-section-header">
            <CreditCard size={16} strokeWidth={2} />
            <h3 className="tf-settings-section-title">Billing</h3>
          </div>
          <div className="tf-settings-section-body">
            <div className="tf-settings-item">
              <div className="tf-settings-item-info">
                <div className="tf-settings-item-label">Current Plan</div>
                <div className="tf-settings-item-desc">Pro — $29/month</div>
              </div>
              <button type="button" className="tf-btn ghost">Manage</button>
            </div>
            <div className="tf-settings-item">
              <div className="tf-settings-item-info">
                <div className="tf-settings-item-label">Usage This Month</div>
                <div className="tf-settings-item-desc">$12.40 / $100 included credits</div>
              </div>
              <button type="button" className="tf-btn ghost">View Details</button>
            </div>
          </div>
        </section>
      </div>
    </PageShell>
  );
};

export default SettingsPage;
