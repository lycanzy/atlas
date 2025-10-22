# Experiment Tracking App - IT Deployment Request

**Date**: October 22, 2025  
**Requested By**: [Your Name]  
**Department**: [Your Lab/Department]  
**Purpose**: Internal experiment tracking and documentation system

---

## Executive Summary for IT Team

We've developed a web-based **Experiment Tracking Application** to help our lab manage and document research experiments. This is a **low-risk, internal-only Django application** that needs to be deployed on an internal server accessible only within our network.

### Key Points:
- ✅ **Internal use only** - No public internet exposure needed
- ✅ **Small user base** - 5-20 researchers in our lab
- ✅ **Minimal resources** - Runs on SQLite, no database server needed
- ✅ **Standard technology** - Python/Django (widely supported)
- ✅ **Security reviewed** - CSRF protection enabled, DEBUG disabled
- ✅ **Low maintenance** - Self-contained application, minimal IT overhead

---

## What We Need From IT

### 1. **Server Access** (Preferred Option)

**Option A: Dedicated Virtual Machine**
- **OS**: Linux (Ubuntu 22.04/24.04 or RHEL 8/9) or Windows Server
- **Resources**: 
  - 2 CPU cores
  - 4GB RAM
  - 20GB disk space
- **Network**: Internal network only (no public internet access required)
- **Access**: SSH/RDP access for initial setup and maintenance

**Option B: Shared Application Server**
- If you have an existing internal web application server
- Can run alongside other internal apps
- Isolated Python virtual environment

### 2. **Software Prerequisites**

The server needs:
- **Python 3.9+** (we're using Python 3.13)
- **Web server**: Nginx or Apache (for serving static files)
- **WSGI server**: Gunicorn or uWSGI (for running Django)

*We can handle the Python environment setup if you provide the base system.*

### 3. **Network Configuration**

- **Hostname**: Something like `experiment-app.yourlab.edu` or `experiment-tracking.internal`
- **Port**: Standard HTTP (80) or HTTPS (443) if you have SSL certificates
- **Access**: Internal network only (firewall rules to block external access)
- **VPN**: If you want remote access for researchers working from home

### 4. **Backup Strategy** (Optional but Recommended)

- **Database**: One SQLite file (`db.sqlite3`) - needs daily backup
- **Backup size**: Currently <10MB, will grow slowly
- **Backup method**: Simple file copy to backup location
- **Retention**: 30 days recommended

---

## Why This Is Easy for IT

### 🟢 **Low Complexity**
- **No database server required** - Uses SQLite (single file)
- **No external dependencies** - Runs entirely on one server
- **No complex configuration** - Standard Django deployment
- **No license costs** - Open source stack (Python, Django, Nginx)

### 🟢 **Low Risk**
- **Internal only** - Not exposed to internet threats
- **Read-only for most operations** - Researchers document their work
- **No sensitive data** - Lab experiment notes (check if applicable)
- **Easy rollback** - SQLite file can be restored from backup

### 🟢 **Low Maintenance**
- **No scheduled jobs** - Simple web application
- **No real-time requirements** - Not mission-critical
- **Infrequent updates** - Stable after initial deployment
- **Self-service admin** - We can manage users through Django admin

### 🟢 **Standard Technology**
- **Django** - Mature Python web framework (used by Instagram, Mozilla, NASA)
- **Battle-tested** - 15+ years of production use worldwide
- **Well-documented** - Extensive community support
- **Security updates** - Active development and patching

---

## Deployment Timeline

| Phase | Task | Duration | Who |
|-------|------|----------|-----|
| **Phase 1** | IT provisions server/VM | 1-2 days | IT Team |
| **Phase 2** | Install Python & dependencies | 2-3 hours | Us (or IT) |
| **Phase 3** | Deploy application | 1-2 hours | Us |
| **Phase 4** | Configure web server (Nginx) | 1-2 hours | IT Team |
| **Phase 5** | Testing & validation | 1 day | Us + IT |
| **Total** | | **3-5 days** | |

---

## Technical Deployment Details (For IT Team)

### Architecture Overview
```
[Researcher Browser] 
    ↓ HTTP/HTTPS
[Nginx Web Server] (serves static files, reverse proxy)
    ↓
[Gunicorn WSGI Server] (runs Django application)
    ↓
[SQLite Database File] (db.sqlite3)
```

### Installation Steps (High-Level)

```bash
# 1. Install system dependencies
sudo apt-get update
sudo apt-get install python3.11 python3-pip python3-venv nginx

# 2. Create application directory
sudo mkdir -p /opt/experiment-app
sudo chown <your-user>: /opt/experiment-app

# 3. Deploy application code
cd /opt/experiment-app
# Upload our application files here

# 4. Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Configure application
# Edit settings.py to set ALLOWED_HOSTS = ['your-server.internal']

# 6. Initialize database
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser

# 7. Configure Gunicorn service
# Create systemd service file

# 8. Configure Nginx
# Create Nginx site configuration

# 9. Start services
sudo systemctl start experiment-app
sudo systemctl start nginx
```

### Resource Usage (Actual)
- **Memory**: ~200MB RAM during normal operation
- **CPU**: <5% on 2-core system with 10 concurrent users
- **Disk**: ~50MB application + database grows ~1MB per 100 experiments
- **Network**: Minimal (mostly text data, some small images)

### Ports Required
- **Application**: 8000 (internal, Gunicorn)
- **Web Server**: 80 (HTTP) or 443 (HTTPS)
- No incoming internet connections required

### Security Measures Already Implemented
- ✅ CSRF protection enabled
- ✅ DEBUG mode disabled for production
- ✅ SQL injection protection (Django ORM)
- ✅ XSS protection (Django templates auto-escape)
- ✅ User authentication required for all operations
- ✅ Password hashing (PBKDF2 with SHA256)

---

## Support & Maintenance Plan

### Our Responsibilities
- ✅ User management (creating accounts, resetting passwords)
- ✅ Data management (experiment entries, cleanup if needed)
- ✅ Application updates (when needed)
- ✅ First-level troubleshooting (user issues)

### IT Team Responsibilities
- ✅ Server uptime and availability
- ✅ Database backups
- ✅ System-level security updates (OS, Python)
- ✅ Network connectivity
- ✅ SSL certificate renewal (if using HTTPS)

### Expected IT Time Commitment
- **Initial setup**: 4-6 hours
- **Ongoing maintenance**: <1 hour per month
- **Support requests**: Rare (application is straightforward)

---

## Alternatives We Considered

| Option | Why We Didn't Choose It |
|--------|------------------------|
| **Excel/Spreadsheets** | No concurrent access, version control nightmares, no validation |
| **SharePoint** | Complex for our needs, poor user experience for forms |
| **Commercial LIMS** | Expensive ($5k-50k/year), overkill for our scale |
| **Cloud SaaS** | Data sovereignty concerns, recurring costs, requires internet |
| **Paper notebooks** | Not searchable, easy to lose, poor collaboration |

---

## Success Metrics

After deployment, we expect:
- ✅ 100% of lab experiments documented digitally (vs. 60% in notebooks)
- ✅ 50% reduction in time spent searching for past experiments
- ✅ Better collaboration (everyone sees same data)
- ✅ Audit trail for all experiment modifications
- ✅ Exportable data for publications/reports

---

## Compliance & Data Considerations

**Data Classification**: [Check with your institution]
- [ ] Public
- [x] Internal Use Only
- [ ] Confidential
- [ ] Restricted

**Data Retention**: Indefinite (research records)

**Data Backup**: Daily recommended

**User Data**: Usernames, passwords (hashed), experiment notes

**PII/PHI**: None (unless experiment notes contain participant data - check your use case)

**Compliance**: [List any applicable regulations]
- [ ] HIPAA (if biomedical research with patient data)
- [ ] FERPA (if educational research)
- [ ] GDPR (if EU researchers)
- [x] General institutional data policies

---

## FAQs for IT Team

### Q: Why not use [existing system we have]?
**A**: We evaluated it, but it's designed for [different purpose]. Our app is specifically designed for experiment flow documentation with multi-step processes and component tracking.

### Q: What if it breaks in production?
**A**: 
1. It's not mission-critical - researchers can fall back to notebooks temporarily
2. SQLite file can be restored from backup in minutes
3. Application can be restarted easily
4. We're available for troubleshooting

### Q: How do we handle user authentication?
**A**: Django's built-in authentication system. We can integrate with LDAP/Active Directory if you prefer (requires additional configuration).

### Q: What about updates and patches?
**A**: 
- Django security updates are released promptly
- We'll test updates in development before deploying
- Updates typically take <30 minutes
- Can be scheduled during low-usage times

### Q: Can this scale if we get more users?
**A**: Yes! Current setup handles 20 concurrent users. If we grow beyond 50 users, we can migrate to PostgreSQL (2-3 hours work) and add caching. Architecture supports horizontal scaling.

### Q: What if you leave the organization?
**A**: 
- Code is well-documented
- Standard Django application (any Python developer can maintain)
- Admin documentation provided
- Can train another team member

---

## Contact Information

**Primary Contact**: [Your Name]  
**Email**: [your.email@institution.edu]  
**Phone**: [Your Phone]  
**Department**: [Your Lab/Department]  
**Supervisor**: [PI/Lab Director Name] (for approval)

**For Technical Questions**: Available for phone/video meeting to discuss details

---

## Approval & Sign-off

**Lab Director Approval**: _________________________ Date: _______

**IT Manager Approval**: _________________________ Date: _______

**Security Review** (if required): _________________________ Date: _______

---

## Appendix: Sample Screenshots

[Consider adding 2-3 screenshots showing:]
1. Login page
2. Main experiment list page
3. Experiment detail page with flows and steps

This helps IT team visualize what they're deploying.

---

## Next Steps

1. **Review this document** with IT team
2. **Schedule kickoff meeting** (30 minutes)
3. **IT provisions server** (1-2 days)
4. **We deploy and test** (1 day)
5. **IT final review and go-live** (1 day)
6. **Training for lab users** (we handle this)

**Estimated Go-Live**: 1 week from approval

---

*This deployment is low-risk, high-value for our research productivity. We appreciate IT's support!*
