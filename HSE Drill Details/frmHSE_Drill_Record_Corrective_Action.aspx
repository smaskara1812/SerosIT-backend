<%@ Page Language="C#" AutoEventWireup="true" CodeFile="frmHSE_Drill_Record_Corrective_Action.aspx.cs"
    Inherits="Quality_And_Safety_Drills_frmHSE_Drill_Record_Corrective_Action" %>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1" runat="server">
    <title>HSE Drill Record Corrective Action</title>

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
 


         
        function ShowMainData() {
            SetPostbackFlag("SEARCH");
            Open_Search_Window('EQUIPMENT_PART', document.forms[0].name, 'tbDrill_Rec_Corrective_Action_Id_Hidden', 'tbEquip_Make_Name', '', '', 'Y', 'N', 'N');
            return;
        }
        
           
        /// Determine whether page has to be posted back by passing a flag to a hidden textbox.
        function SetPostbackFlag(strFlag) {
            document.getElementById('<%=tbPostbackFlag_Hidden.ClientID%>').value = strFlag;
            return true;
        } 

        function ValidateInsert(lnkUpdate, Type) {
            SetPostbackFlag(Type);
            var msg = "";
            var strServerDt = '<%= Session["ServerDt"].ToString() %>';
             

             
            var grdRow = lnkUpdate.parentNode.parentNode;
            var grdControl = grdRow.getElementsByTagName("input");

           
            var tbDrill_Rec_Corrective_Action_Desc = grdRow.getElementsByTagName("textarea")[0];//.id;
             

            if (alltrim(tbDrill_Rec_Corrective_Action_Desc.value) == "") {
                msg += "- Corrective Action Taken must be entered.<br><br>";

            }

            if (msg == "") {

                return true;

            }
            else {
                ShowErrorWin1(msg);
                return false;
            }
        }

        function ValidateUpdate(lnkUpdate, Type) {


            SetPostbackFlag(Type);
            var msg = "";
            var strServerDt = '<%= Session["ServerDt"].ToString() %>';

             
            var grdRow = lnkUpdate.parentNode.parentNode;
            var grdControl = grdRow.getElementsByTagName("input");
            
            var tbDrill_Rec_Corrective_Action_Desc = grdRow.getElementsByTagName("textarea")[0];//.id;

            
            if (alltrim(tbDrill_Rec_Corrective_Action_Desc.value) == "") {
                msg += "- Observation must be entered.<br><br>";
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

            var rows = document.getElementById('<%=grdImprovement.ClientID %>').getElementsByTagName('TR');
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
    <form id="frmHSE_Drill_Record_Corrective_Action" runat="server">
        <div style="left: 0px; width: 100%; position: absolute; top: 0px; height: 88%">
            <table style="width: 100%" class="table_header">
                <tr>
                   
                    <td class="td_button">
                        <asp:Button ID="btnSearch" runat="server" Text="Search" Width="100%" CssClass="td_button" Visible="false" />

                    </td>
             

                    <td class="td_button">
                        <asp:Button ID="btnClear" runat="server" Text="Clear" Width="100%" CssClass="td_button" Visible="false"/></td>

                    <td class="td_button">&nbsp;</td>
                    <td class="td_header" style="width: 46%">Corrective Action Taken</td>
                </tr>
            </table>
            <br />
             
            <table class="table">
                <tr>
                    <td style="width:2%">&nbsp;</td>
                </tr>
                <tr>
                    <td></td>
                    <td>

                           <div id="divHelpData" class="div_gridview" style="width: 75%;">
                        <asp:GridView ID="grdImprovement" CssClass="GridView" Width="98%" runat="server"
                            AutoGenerateColumns="False" DataKeyNames="Drill_Rec_Corrective_Action_Id"
                            ShowFooter="True" OnRowCommand="grdImprovement_RowCommand" OnRowUpdating="grdImprovement_RowUpdating" OnRowCancelingEdit="grdImprovement_RowCancelingEdit" OnRowEditing="grdImprovement_RowEditing">   
                            <Columns>
                                <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="ID" Visible="false">
                                    <EditItemTemplate>
                                        <asp:Label ID="lblId" CssClass="textbox" runat="server" Text='<%# Bind("Drill_Rec_Corrective_Action_Id") %>'></asp:Label>
                                    </EditItemTemplate>
                                    <ItemTemplate>
                                        <asp:Label ID="lblId0" runat="server" Text='<%# Bind("Drill_Rec_Corrective_Action_Id") %>'></asp:Label>
                                    </ItemTemplate>
                                    <ItemStyle />
                                    <HeaderStyle HorizontalAlign="Left"></HeaderStyle>
                                </asp:TemplateField>

                             
                                 <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Corrective Action Taken * (200 Chars.)" ItemStyle-CssClass="textbox" FooterStyle-CssClass="textbox">
                                    <EditItemTemplate>
                                        <asp:TextBox ID="txtEdit_Drill_Rec_Corrective_Action_Desc" runat="server" CssClass="textbox" MaxLength="200" Text='<%# Bind("Drill_Rec_Corrective_Action_Desc") %>'
                                            Width="690px" TextMode="MultiLine" Height="30px" onkeyPress="CheckMaxLen(this,200);"
                                            onblur="return fncMultilineTBOnBlur(this,200);"></asp:TextBox>
                                    </EditItemTemplate>
                                    <FooterTemplate>
                                        <asp:TextBox ID="txtDrill_Rec_Corrective_Action_Desc" runat="server" CssClass="textbox" MaxLength="200"
                                            Width="690px" TextMode="MultiLine" Height="30px" onkeyPress="CheckMaxLen(this,200);"
                                            onblur="return fncMultilineTBOnBlur(this,200);"></asp:TextBox>
                                    </FooterTemplate>
                                    <ItemTemplate>
                                        <asp:Label ID="lblDrill_Rec_Corrective_Action_Desc" runat="server" Text='<%# Bind("Drill_Rec_Corrective_Action_Desc") %>'></asp:Label>
                                    </ItemTemplate>
                                    <HeaderStyle HorizontalAlign="Left" Width="770px"></HeaderStyle>
                                    <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="770px" />
                                    <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="770px" />
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
                                            CommandArgument='<%# Eval("Drill_Rec_Corrective_Action_Id") %>' OnClientClick="javascript:return ChkPrintStatus(this);"></asp:LinkButton>
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
           <input id="tbDrill_Dt_Id_Hidden" runat="server" name="tbDrill_Dt_Id_Hidden"
                style="z-index: 104; left: 312px; width: 24px; position: absolute; top: 289px; height: 24px"
                type="hidden" value="" />
            
            <input id="tbPostbackFlag_Hidden" runat="server" name="tbPostbackFlag_Hidden" style="z-index: 104; left: 165px; width: 24px; position: absolute; top: 291px; height: 24px"
                type="hidden" />
        </div>
    </form>
</body>
</html>
 