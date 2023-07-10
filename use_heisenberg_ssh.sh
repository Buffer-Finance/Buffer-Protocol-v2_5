eval $(ssh-agent -s)
ssh-add ~/.ssh/heisenberg
ssh -T git@github.com
git config user.name "Heisenberg"
git config user.email "buffer_finance@protonmail.com"
