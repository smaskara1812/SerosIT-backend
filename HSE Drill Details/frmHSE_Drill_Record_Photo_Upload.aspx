<%@ Page Language="C#" AutoEventWireup="true" CodeFile="frmHSE_Drill_Record_Photo_Upload.aspx.cs"
    Inherits="Quality_And_Safety_frmHSE_Drill_Record_Photo_Upload" %>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1" runat="server">
    <title>HSE Drill Record Photo Upload</title>

    <link href="../../StyleSheet.css" type="text/css" rel="stylesheet" />
    <script type="text/javascript" language="javascript" src="../../Javascript/generic.js"> </script> 
    <script type="text/javascript" language="javascript" src="../../Javascript/Open_Search.js"> </script>
    <script type="text/javascript" language="javascript" src="../../Javascript/Open_ErrorWin.js"> </script>   
    <script type="text/javascript" language="javascript" src="../../JavaScript/jquery.min.js"></script>
    <script type="text/javascript" language="javascript" src="../../JavaScript/bootstrap.min.js"></script>
    <script type="text/javascript" language="javascript" src="../../JavaScript/CommonModal.js"></script>
    
    <link href="../../BootstrapStyleSheet.min.css" type="text/css" rel="stylesheet" /> 

    <script type="text/javascript">
        window.onload = function () {   }




        //function ShowMainData() {
        //    SetPostbackFlag("SEARCH");
        //    Open_Search_Window('EQUIPMENT_PART', document.forms[0].name, 'tbDrill_Rec_Photo_Upload_Id_Hidden', 'tbEquip_Make_Name', '', '', 'Y', 'N', 'N');
        //    return;
        //}


        /// Determine whether page has to be posted back by passing a flag to a hidden textbox.
        function SetPostbackFlag(strFlag) {
            document.getElementById('<%=tbPostbackFlag_Hidden.ClientID%>').value = strFlag;
            return true;
        }
        function Image_Window(URL) {
            var New_window = window.open(URL, '_blank', 'left=0,top=0,height=500,width=500, resizable=yes, status=yes');
        }

        function ValidateInsert(lnkUpdate, Type) {
            SetPostbackFlag(Type);
            var msg = "";
            var strServerDt = '<%= Session["ServerDt"].ToString() %>';



            var grdRow = lnkUpdate.parentNode.parentNode;
            var grdControl = grdRow.getElementsByTagName("input");

           // var tbDrill_Rec_Photo_Active = grdRow.getElementsByTagName("input")[1];

            var tbfupd_Certificate_Path = grdRow.getElementsByTagName("input")[0];//.id;
             
            if (tbfupd_Certificate_Path.value == "") {
                msg += "- Photo must be selected for uploading.<br><br>";
            }


            if (msg == "") {

                return true;

            }
            else {
                ShowErrorWin1(msg);
                return false;
            }
        }

        function checked_YN(obj) {
            if (document.getElementById(obj.id).value != "") {

                if (document.getElementById(obj.id).value == "y" || document.getElementById(obj.id).value == "Y") {
                    document.getElementById(obj.id).value = "Y";
                }
                else if (document.getElementById(obj.id).value == "n" || document.getElementById(obj.id).value == "N") {
                    document.getElementById(obj.id).value = "N";
                }
                else {
                    document.getElementById(obj.id).value = "";
                }
            }
        }

        function ValidateUpdate(lnkUpdate, Type) {


            SetPostbackFlag(Type);
            var msg = "";
            var strServerDt = '<%= Session["ServerDt"].ToString() %>';


            var grdRow = lnkUpdate.parentNode.parentNode;
            var grdControl = grdRow.getElementsByTagName("input");


            

            var fupd_Certificate_Path_Edit_Item = grdRow.getElementsByTagName("input")[0];

            var txtEdit_Drill_Rec_Photo_Active = grdRow.getElementsByTagName("input")[1];

            var tbDrill_Rec_Photo_Upload_Path_Hidden = grdRow.getElementsByTagName("input")[2];
 

            var res = tbDrill_Rec_Photo_Upload_Path_Hidden.value.substring(0, 1); 
            //check the first characters 

            if (txtEdit_Drill_Rec_Photo_Active.value == "") {
                msg += "- Active(Y/N) must be entered.<br><br>";

            }
            else {
                if (txtEdit_Drill_Rec_Photo_Active.value == "Y" || txtEdit_Drill_Rec_Photo_Active.value == "y") {

                    if (res == "N")///if file is not uploaded and user selecting active =Y' then flash the message.
                    {
                        if (fupd_Certificate_Path_Edit_Item.value == "")
                        {
                            msg += "- Photo must be selected for uploading.<br><br>";

                        }
                    }
                }
            }
            if (msg == "") {
                return true;
            }
            else {
                ShowErrorWin1(msg);
                return false;
            }
        }



        function ChkPrintStatus(id) {

            var rows = document.getElementById('<%=grdContact.ClientID %>').getElementsByTagName('TR');
               for (var i = 0; i < rows.length; i++) {
                   rows[i].className = 'GridView_RowStyle'; //if its your default color
               }
               document.getElementById(id.uniqueID).parentNode.parentNode.className = 'GridView_SelectedRowStyle';


               var chkdeletestatus = confirm("Are you sure you want to Delete this Record?");
               if (chkdeletestatus == true) {
                   return true;
               }
               else {
                   document.getElementById(id.uniqueID).parentNode.parentNode.className = 'GridView_RowStyle';
                   return false;
               }
           }

           function CheckMaxLen(obj, length) {
               checkTextAreaMaxLength(obj, event, length);
           }
    </script>

</head>
<body class="body" onkeydown="if (event.keyCode==13) {event.keyCode=9; return event.keyCode }">
    <form id="frmHSE_Drill_Record_Event" runat="server">
        <div style="left: 0px; width: 100%; position: absolute; top: 0px; height: 88%">
            <table style="width: 100%" class="table_header">
                <tr>
                  
                    <td class="td_button">
                        <asp:Button ID="btnSearch" runat="server" Text="Search" Width="100%" CssClass="td_button" Visible="false" />
                    </td>
                    <td class="td_button">
                        <asp:Button ID="btnClear" runat="server" Text="Clear" Width="100%" CssClass="td_button" Visible="false"/>
                    </td>
                    <td class="td_button">&nbsp;</td>
                    <td class="td_header" style="width: 46%">Chronological Order of Events during the Drill</td>
                </tr>
            </table>
            <br />
            <table class="table">
                <tr>
                    <td style="width: 2%">&nbsp;</td>
                </tr>
                <tr>
                    <td></td>
                    <td>

                        <div id="divHelpData" class="div_gridview"  style="width: 75%;">
                            <asp:GridView ID="grdContact" CssClass="GridView" Width="98%" runat="server"
                                AutoGenerateColumns="False" DataKeyNames="Drill_Rec_Photo_Upload_Id"
                                ShowFooter="True" OnRowCommand="grdContact_RowCommand" OnRowUpdating="grdContact_RowUpdating" OnRowCancelingEdit="grdContact_RowCancelingEdit" OnRowEditing="grdContact_RowEditing" OnRowDataBound="grdContact_RowDataBound">
                                <Columns>
                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="ID" Visible="false">
                                        <EditItemTemplate>
                                            <asp:Label ID="lblId" CssClass="textbox" runat="server" Text='<%# Bind("Drill_Rec_Photo_Upload_Id") %>'></asp:Label>
                                        </EditItemTemplate>
                                        <ItemTemplate>
                                            <asp:Label ID="lblId0" runat="server" Text='<%# Bind("Drill_Rec_Photo_Upload_Id") %>'></asp:Label>
                                        </ItemTemplate>
                                        <ItemStyle />
                                        <HeaderStyle HorizontalAlign="Left"></HeaderStyle>
                                    </asp:TemplateField>                                    
                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Upload Photo">
                                        <ItemTemplate>
                                            <a href="#" id="lnkDisp_Img" runat="server">Show</a>
                                        </ItemTemplate>
                                        <EditItemTemplate>
                                                <asp:FileUpload ID="fupd_Certificate_Path_Edit_Item" CssClass="textbox_readonly" onkeydown="return false;"
                                                name="uploadFile" onchange="return SetPostbackFlag('IMG_UPLOAD');"
                                                runat="server"   />
                                                <asp:Label ID="lblFile" runat="server" Text= "* File size must not exceed 100 kb"></asp:Label>
                                                <asp:Label ID="Label1" runat="server" Text= ".gif, .png, .jpeg, .jpg"></asp:Label>  </EditItemTemplate>
                                        <FooterTemplate>
                                              
                                            <asp:FileUpload ID="fupd_Certificate_Path" CssClass="textbox_readonly" onkeydown="return false;"
                                                name="uploadFile" onchange="return SetPostbackFlag('IMG_UPLOAD');" 
                                                runat="server" />                                            
                                             <asp:Label ID="lblFile" runat="server" Text= "* File size must not exceed 5 MB" Width="100%"></asp:Label>
                                             <asp:Label ID="Label1" runat="server" Text= "* file ext :.gif .png .jpeg .jpg" Width="100%"></asp:Label>
                                        </FooterTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="500px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="500px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="500px" />
                                    </asp:TemplateField>
                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Active(Y/N)*" ItemStyle-CssClass="textbox" FooterStyle-CssClass="textbox">
                                        <EditItemTemplate>
                                            <asp:TextBox ID="txtEdit_Drill_Rec_Photo_Active" runat="server" Text='<%# Bind("Drill_Rec_Photo_Active") %>' CssClass="textbox"
                                                Height="15px" MaxLength="1" onKeyUp="checked_YN(this);" Width="10px"></asp:TextBox>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:TextBox ID="txtDrill_Rec_Photo_Active" runat="server" CssClass="textbox"
                                                Height="15px" MaxLength="1" onKeyUp="checked_YN(this);" Width="10px" Visible="false"></asp:TextBox>
                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:Label ID="lblDrill_Rec_Photo_Active" runat="server" Text='<%# Bind("Drill_Rec_Photo_Active") %>'></asp:Label>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="80px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="80px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="80px" />
                                    </asp:TemplateField>

                                    <asp:TemplateField HeaderStyle-CssClass="hiddencol" HeaderText="tbDrill_Rec_Photo_Upload_Path_Hidden"
                                        ItemStyle-CssClass="hiddencol">
                                        <ItemTemplate>
                                            <input id="tbDrill_Rec_Photo_Upload_Path_Hidden" runat="server" name="tbDrill_Rec_Photo_Upload_Path_Hidden"
                                                style="z-index: 104; left: 43px; width: 24px; position: absolute; top: 258px; height: 24px"
                                                type="hidden" value='<%# Bind("Drill_Rec_Photo_Upload_Path") %>' />
                                        </ItemTemplate>
                                        <HeaderStyle CssClass="hiddencol"></HeaderStyle>
                                        <ItemStyle CssClass="hiddencol"></ItemStyle>
                                    </asp:TemplateField>
                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Insert" ShowHeader="False">
                                        <EditItemTemplate>
                                            <asp:LinkButton ID="lbkUpdate" runat="server" CausesValidation="True" CommandName="Update" Text="Update" OnClientClick="return ValidateUpdate(this,'Update')"></asp:LinkButton>
                                            <asp:LinkButton ID="lnkCancel" runat="server" CausesValidation="False" CommandName="Cancel" Text="Cancel"></asp:LinkButton>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:LinkButton ID="lnkAdd" runat="server" CausesValidation="False" CommandName="Insert" Text="Insert" OnClientClick="return ValidateInsert(this,'Insert')"></asp:LinkButton>
                                        </FooterTemplate>

                                        <ItemTemplate>
                                            <asp:LinkButton ID="lnkEdit" runat="server" CausesValidation="False" CommandName="Edit" Text="Edit"></asp:LinkButton>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="120px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="120px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="120px" />
                                    </asp:TemplateField>

                                    <asp:TemplateField HeaderText="Delete">
                                        <EditItemTemplate>
                                            <asp:LinkButton ID="ilnkDelete" runat="server"></asp:LinkButton>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:LinkButton ID="lnkDelete" runat="server"></asp:LinkButton>
                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:LinkButton ID="lnkDelete" CommandName="cmdDelete" Text="Delete" runat="server"
                                                CommandArgument='<%# Eval("Drill_Rec_Photo_Upload_Id") %>' OnClientClick="javascript:return ChkPrintStatus(this);"></asp:LinkButton>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="120px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="120px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="120px" />
                                    </asp:TemplateField>
                                </Columns>

                                   <RowStyle CssClass="GridView_RowStyle" />
                             
                            <SelectedRowStyle CssClass="GridView_SelectedRowStyle" />
                            <HeaderStyle  CssClass="GridView_HeaderStyle" Height="20px" />
                            <AlternatingRowStyle CssClass="GridView_AlternatingRowStyle" />
                        </asp:GridView>
                            
                        </div>
                    </td>
                </tr>
            </table>

            <input id="tbDrill_Record_Hdr_Id_Hidden" runat="server" name="tbDrill_Record_Hdr_Id_Hidden"
                style="z-index: 104; left: 312px; width: 24px; position: absolute; top: 289px; height: 24px"
                type="hidden" value="" />
            

            <input id="tbPostbackFlag_Hidden" runat="server" name="tbPostbackFlag_Hidden" style="z-index: 104; left: 165px; width: 24px; position: absolute; top: 291px; height: 24px"
                type="hidden" />
        </div>
    </form>
</body>
</html>
