terraform {
  required_version = ">= 1.7"
}

variable "host" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9.-]*$", var.host))
    error_message = "Use a DNS name or IPv4 address."
  }
}
variable "user" {
  type = string
  validation {
    condition     = can(regex("^[a-z_][a-z0-9_-]*$", var.user))
    error_message = "Use a simple SSH user name."
  }
}
variable "image" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._:/@-]*$", var.image))
    error_message = "Use a registry image without shell metacharacters."
  }
}

resource "terraform_data" "container" {
  triggers_replace = [var.image, var.host, var.user]
  provisioner "local-exec" {
    environment = { TARGET_HOST = var.host, TARGET_USER = var.user, TARGET_IMAGE = var.image }
    command     = <<-SHELL
      ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "$TARGET_USER@$TARGET_HOST" \
        "set -e; docker pull '$TARGET_IMAGE'; docker rm -f lumentrail >/dev/null 2>&1 || true; docker run -d --name lumentrail --restart unless-stopped --read-only --cap-drop ALL --security-opt no-new-privileges -p 127.0.0.1:8080:8080 -e LUMENTRAIL_BEHIND_TLS_PROXY=1 --env-file /etc/lumentrail/api.env '$TARGET_IMAGE'"
    SHELL
  }
}

output "ssh_tunnel" { value = "ssh -L 8080:127.0.0.1:8080 ${var.user}@${var.host}" }
